# pylint: disable=import-error, line-too-long, relative-beyond-top-level
"""Quizer backend"""
import random
import traceback
import json
from datetime import datetime, timedelta
from jwt import DecodeError
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect, reverse
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views import View
from . import mongo
from . import utils
from .decorators import unauthenticated_user, allowed_users, post_method
from .models import Test, Subject
from .forms import SubjectForm, TestForm


@unauthenticated_user
@allowed_users(allowed_roles=['lecturer'])
def questions(request, test_id: int):
    test = Test.objects.get(id=test_id)
    if not test:
        return redirect(reverse('main:available_tests'))
    storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
    test_questions = storage.get_many(test_id=test.id)
    for question in test_questions:
        question['id'] = str(question.pop('_id'))
    context = {
        'title': 'Вопросы',
        'test': test,
        'questions': test_questions
    }
    return render(request, 'main/lecturer/managingQuestions.html', context)


def login_page(request):
    """Authorize user and redirect him to available_tests page"""
    logout(request)
    try:
        username, group = utils.get_auth_data(request)
    except DecodeError:
        return HttpResponse('JWT decode error: %s' % traceback.format_exc().replace('File', '<br><br>File'))
    user = authenticate(username=username, password='')
    if user is None:
        group2id = {
            'dev': 1,
            'admin': 1,
            'teacher': 1,
            'student': 2
        }
        if group in ['student', 'teacher']:
            user = User(username=username, password='')
        elif group in ['dev', 'admin']:
            user = User.objects.create_superuser(username=username, email='', password='')
        else:
            return HttpResponse('Incorrect group.')
        user.save()
        user.groups.add(group2id[group])
    login(request, user)
    mongo.set_conn(
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
        db_name=settings.DATABASES['default']['NAME'])
    return redirect(reverse('main:available_tests'))


class AvailableTestsView(View):
    """View for available tests"""
    lecturer_template = 'main/lecturer/availableTests.html'
    student_template = 'main/student/availableTests.html'
    title = 'Доступные тесты'
    context = {}
    decorators = [unauthenticated_user]

    @method_decorator(decorators)
    def get(self, request):
        """
        Page to which user is redirected after successful authorization
        For lecturer - displays list of tests that can be run
        For student - displays list of running tests
        """
        storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
        running_tests = storage.get_running_tests()
        running_tests_ids = [test['test_id'] for test in running_tests]
        if request.user.groups.filter(name='lecturer'):
            return self.lecturer_available_tests(request, running_tests_ids)
        return self.student_available_tests(request, running_tests)

    @method_decorator(decorators)
    def post(self, request):
        """Configuring running tests"""
        if 'lecturer-running-test-id' in request.POST:
            self.lecturer_launch_test(request)
        elif 'lecturer-passed-test' in request.POST:
            self.lecturer_passed_test_result(request)
        elif 'run-test' in request.POST:
            return self.run_test(request)
        else:
            self.context = {}
        return self.get(request)

    def lecturer_available_tests(self, request, running_tests_ids: list):
        """Tests available for launching by lecturers"""
        tests = Test.objects.all()
        not_running_tests = [t for t in tests if t.id not in running_tests_ids]
        self.context = {
            **self.context,
            'title': self.title,
            'subjects': list(Subject.objects.all()),
            'tests': json.dumps([t.to_dict() for t in not_running_tests]),
        }
        return render(request, self.lecturer_template, self.context)

    def student_available_tests(self, request, running_tests: list):
        """Tests available for running by students"""
        if len(running_tests) == 0:
            self.context = {
                'title': self.title,
                'message_title': 'Доступные тесты отсутствуют',
                'message': 'Ни один из тестов пока не запущен.',
            }
            return render(request, self.student_template, self.context)
        self.context = {
            'title': self.title,
            'tests': [
                {
                    'launched_lecturer': User.objects.get(id=test['launched_lecturer_id']),
                    **Test.objects.get(id=test['test_id']).to_dict()
                }
                for test in running_tests
            ]
        }
        return render(request, self.student_template, self.context)

    def lecturer_launch_test(self, request):
        """Launching test for students"""
        test = Test.objects.get(id=int(request.POST['lecturer-running-test-id']))
        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        questions = storage.get_many(test_id=test.id)
        if len(questions) < test.tasks_num:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': "Тест '%s' не запущен, так как вопросов в базе меньше %d."
                                 % (test.name, test.tasks_num)
            }
        else:
            storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
            storage.add_running_test(
                test_id=test.id,
                lecturer_id=request.user.id,
                subject_id=test.subject.id)
            self.context = {
                'modal_title': "Тест '%s' запущен" % test.name,
                'modal_message': "Состояние его прохождения можно отследить во вкладке 'Запущенные тесты'."
            }

    def lecturer_passed_test_result(self, request):
        """Test results"""
        storage = mongo.RunningTestsAnswersStorage.connect(db=mongo.get_conn())
        passed_test_answers = storage.get(user_id=request.user.id)

        test_id = passed_test_answers['test_id']
        storage.delete(user_id=request.user.id)

        result = utils.get_test_result(
            request=request,
            right_answers=passed_test_answers['right_answers'],
            test_duration=passed_test_answers['test_duration'])

        storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
        storage.add_results_to_running_test(
            test_result=result,
            test_id=test_id)

        self.context = {
            'title': 'Доступные тесты',
            'modal_title': 'Результат',
            'modal_message': 'Число правильных ответов: %d/%d' % (result['right_answers_count'], result['tasks_num'])
        }
        return render(request, self.lecturer_template, self.context)

    def run_test(self, request):
        """Running available test"""
        test = Test.objects.get(id=int(request.POST['test_id']))

        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        test_questions = storage.get_many(test_id=test.id)
        if request.user.groups.filter(name='lecturer') and len(test_questions) < test.tasks_num:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': "Тест '%s' не запущен, так как вопросов в базе меньше %d."
                                 % (test.name, test.tasks_num)
            }
            return self.get(request)
        test_questions = random.sample(test_questions, k=test.tasks_num)
        for question in test_questions:
            random.shuffle(question['options'])

        right_answers = {}
        for i, question in enumerate(test_questions):
            right_answers[str(i + 1)] = {
                'right_answers': [option for option in question['options'] if option['is_true']],
                'id': str(question['_id'])
            }
        storage = mongo.RunningTestsAnswersStorage.connect(db=mongo.get_conn())
        docs = storage.cleanup(user_id=request.user.id)
        storage.add(
            right_answers=right_answers,
            test_id=test.id,
            user_id=request.user.id,
            test_duration=test.duration)
        for test_answers in docs:
            result = utils.get_test_result(
                request=request,
                right_answers=test_answers['right_answers'],
                test_duration=test_answers['test_duration'])
            storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
            storage.add_results_to_running_test(
                test_result=result,
                test_id=test.id)
        self.context = {
            'title': 'Тест',
            'questions': test_questions,
            'test_duration': test.duration,
            'test_name': test.name,
            'right_answers': right_answers,
        }
        if request.user.groups.filter(name='student'):
            return render(request, 'main/student/runTest.html', self.context)
        return render(request, 'main/lecturer/runTest.html', self.context)


class SubjectsView(View):
    """Configuring study subject view"""
    template = 'main/admin/subjects.html'
    title = 'Учебные предметы'
    context = {}
    decorators = [unauthenticated_user, allowed_users(allowed_roles=['admin'])]

    @method_decorator(decorators)
    def get(self, request):
        """Displays page with all subjects"""
        self.context = {
            **self.context,
            'title': self.title,
            'form': SubjectForm(),
            'subjects': [
                (subject, Test.objects.filter(subject__id=subject.id).count())
                for subject in Subject.objects.all()
            ]
        }
        return render(request, self.template, self.context)

    @method_decorator(decorators)
    def post(self, request):
        """Configuring subjects"""
        form = SubjectForm(request.POST)
        if 'add' in request.POST:
            self.add_subject(form)
        elif 'edit' in request.POST:
            self.edit_subject(request)
        elif 'delete' in request.POST:
            self.delete_subject(request)
        elif 'load' in request.POST:
            self.load_subject(request, form)
        else:
            self.context = {}
        return self.get(request)

    def add_subject(self, form: SubjectForm) -> None:
        """Adding new study subject"""
        if form.is_valid():
            subject = Subject(
                name=form.cleaned_data.get('name'),
                description=form.cleaned_data.get('description'))
            subject.save()
            self.context = {
                'modal_title': 'Новый предмет',
                'modal_message': "Предмет '%s' успешно добавлен." % subject.name
            }
        else:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Форма добавления некорректно заполнена.'
            }

    def load_subject(self, request, form: SubjectForm):
        """Loading new subject with tests"""
        if form.is_valid():
            self.context = {
                'modal_title': 'Новый предмет',
                'modal_message': utils.add_subject_with_tests(request, form)
            }
        else:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Форма загрузки некорректно заполнена.'
            }

    def edit_subject(self, request):
        """Editing study subject"""
        name = request.POST['name']
        subject_id = int(request.POST['subject_id'])
        Subject.objects.filter(id=subject_id).update(**dict(
            name=name,
            description=request.POST['description']))
        self.context = {
            'modal_title': 'Предмет отредактирован',
            'modal_message': f"Предмет '{name}' успешно изменен."
        }

    def delete_subject(self, request):
        """Deleting study subjects with all tests and questions"""
        subject_id = int(request.POST['subject_id'])
        subject = Subject.objects.get(id=subject_id)
        subject_name = subject.name
        tests = Test.objects.filter(subject__id=subject.id)
        tests_count = tests.count()
        deleted_questions_count = 0
        for test in tests:
            storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
            deleted_questions_count += storage.delete_many(test_id=test.id)
        subject.delete()
        result = "Учебный предмет '%s', %d тестов к нему, а также все " + \
                 "вопросы к тестам в количестве %d были успешно удалены."
        self.context = {
            'modal_title': 'Предмет удален',
            'modal_message': result % (subject_name, tests_count, deleted_questions_count)
        }


class TestsView(View):
    """Configuring tests view"""
    template = 'main/lecturer/tests.html'
    title = 'Тесты'
    context = {}
    decorators = [unauthenticated_user, allowed_users(allowed_roles=['lecturer'])]

    @method_decorator(decorators)
    def get(self, request):
        """Displays page with all tests"""
        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        tests = [t.to_dict() for t in Test.objects.all()]
        for test in tests:
            test['questions_num'] = len(storage.get_many(test_id=test['id']))
        self.context = {
            **self.context,
            'title': self.title,
            'subjects': list(Subject.objects.all()),
            'tests': json.dumps(tests),
            'form': TestForm()
        }
        return render(request, self.template, self.context)

    @method_decorator(decorators)
    def post(self, request):
        """Configuring tests"""
        form = TestForm(request.POST)
        if 'add' in request.POST:
            self.add_test(request, form)
        elif 'load' in request.POST:
            self.load_test(request, form)
        elif 'edit' in request.POST:
            self.edit_test(request)
        elif 'delete' in request.POST:
            self.delete_test(request)
        elif 'add-question' in request.POST:
            self.add_question(request)
        elif 'load-questions' in request.POST:
            self.load_questions(request)
        elif 'delete-question' in request.POST:
            self.delete_question(request)
        elif 'edit-question' in request.POST:
            self.edit_question(request)
        else:
            self.context = {}
        return self.get(request)

    def add_test(self, request, form: TestForm) -> None:
        """Adding new test"""
        if form.is_valid():
            subject = form.cleaned_data['subject']
            test = Test(
                name=form.cleaned_data['name'],
                author=request.user,
                subject=subject,
                description=form.cleaned_data['description'],
                tasks_num=form.cleaned_data['tasks_num'],
                duration=form.cleaned_data['duration'])
            test.save()
            self.context = {
                'modal_title': 'Новый тест',
                'modal_message': "Тест '%s' по предмету '%s' успешно добавлен." % (test.name, subject)
            }
        else:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Форма добавления некорректно заполнена.'
            }

    def load_test(self, request, form: TestForm):
        """Loading new test from text file"""
        if form.is_valid():
            self.context = {
                'modal_title': 'Новый тест',
                'modal_message': ''
            }
        else:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Форма загрузки некорректно заполнена.'
            }

    def edit_test(self, request):
        """Editing test"""
        Test.objects.filter(id=request.POST['test_id']).update(**dict(
            name=request.POST['name'],
            author=request.user,
            description=request.POST['description'],
            tasks_num=request.POST['tasks_num'],
            duration=request.POST['duration']))
        self.context = {
            'modal_title': 'Тест отредактирован',
            'modal_message': "Тест '%s' успешно изменен." % request.POST['name']
        }

    def delete_test(self, request):
        """Deleting test with all questions"""
        test = Test.objects.get(id=request.POST['test_id'])
        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        deleted_questions_count = storage.delete_many(test_id=test.id)
        message = "Тест '%s' и %d вопросов к нему были успешно удалены."
        self.context = {
            'modal_title': 'Тест удален',
            'modal_message': message % (test.name, deleted_questions_count)
        }
        Test.delete(test)

    def add_question(self, request):
        """Adding new question for test"""
        test = Test.objects.get(id=int(request.POST['test_id']))
        try:
            question = utils.parse_question_form(
                request=request,
                test=test)
            storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
            storage.add_one(
                question=question,
                test_id=test.id)
            message = "Вопрос '%s' к тесту '%s' успешно добавлен."
            self.context = {
                'modal_title': 'Вопрос добавлен',
                'modal_message': message % (question['formulation'], test.name)
            }
        except KeyError:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Форма некорректно заполнена'
            }

    def load_questions(self, request):
        """Loading questions from file"""
        test = Test.objects.get(id=int(request.POST['test_id']))
        try:
            questions_list = utils.get_questions_list(request)
            storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
            for question in questions_list:
                storage.add_one(
                    question=question,
                    test_id=test.id)
            message = "Вопросы к тесту '%s' в количестве %d успешно добавлены."
            self.context = {
                'modal_title': 'Вопросы загружены',
                'modal_message': message % (test.name, len(questions_list))
            }
        except utils.InvalidFileFormatError:
            self.context = {
                'modal_title': 'Ошибка',
                'modal_message': 'Файл некорректного формата.'
            }

    def delete_question(self, request):
        """Deleting questions for test"""
        question_id = request.POST['question_id']
        test_id = int(request.POST['test_id'])
        test = Test.objects.get(id=test_id)

        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        storage.delete_by_id(
            question_id=question_id,
            test_id=test.id)
        self.context = {
            'modal_title': 'Вопрос удален',
            'modal_message': "Вопрос к тесту '%s' был успешно удален." % test.name
        }

    def edit_question(self, request):
        """Editing question for test"""
        test_id = int(request.POST['test_id'])
        test = Test.objects.get(id=test_id)
        updated_params = utils.parse_edit_question_form(request)

        storage = mongo.QuestionsStorage.connect(db=mongo.get_conn())
        if request.POST['with_images'] == 'on':
            storage.update_formulation(
                question_id=request.POST['question_id'],
                formulation=updated_params['formulation']
            )
        else:
            storage.update(
                question_id=request.POST['question_id'],
                formulation=updated_params['formulation'],
                options=updated_params['options']
            )
        message = "Вопрос '%s' к тесту '%s' успешно отредактирован."
        self.context = {
            'modal_title': 'Вопрос отредактирован',
            'modal_message': message % (updated_params['formulation'], test.name)
        }


class PassedTestView(View):
    """View for results of passed tests"""
    template = 'main/student/availableTests.html'
    context = {}
    decorators = [unauthenticated_user, allowed_users(allowed_roles=['student'])]

    @method_decorator(decorators)
    def get(self, _):
        """Redirect user to available tests page"""
        return redirect(reverse('main:available_tests'))

    @method_decorator(decorators)
    def post(self, request):
        """Displays page with results of passing test"""
        if 'test-passed' in request.POST:
            return self.get_passed_test_results(request)
        return self.get(request)

    def get_passed_test_results(self, request):
        """Test results"""
        storage = mongo.RunningTestsAnswersStorage.connect(db=mongo.get_conn())
        passed_test_answers = storage.get(user_id=request.user.id)
        if not passed_test_answers:
            return redirect(reverse('main:available_tests'))
        test_id = passed_test_answers['test_id']
        storage.delete(user_id=request.user.id)

        result = utils.get_test_result(
            request=request,
            right_answers=passed_test_answers['right_answers'],
            test_duration=passed_test_answers['test_duration'])

        storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
        storage.add_results_to_running_test(
            test_result=result,
            test_id=test_id)

        self.context = {
            'title': 'Результаты тестирования',
            'message_title': 'Результат',
            'message': 'Число правильных ответов: %d/%d' % (result['right_answers_count'], result['tasks_num'])
        }
        return render(request, self.template, self.context)


@unauthenticated_user
@allowed_users(allowed_roles=['lecturer'])
def get_running_tests(request):
    """Displays page with running lecturer's tests"""
    storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
    running_tests = storage.get_running_tests()
    tests = []
    for running_test in running_tests:
        if running_test['launched_lecturer_id'] == request.user.id:
            test = Test.objects.get(id=running_test['test_id']).to_dict()
            test_results = storage.get_running_test_results(
                test_id=test['id'],
                lecturer_id=request.user.id)
            results = test_results['results']
            results.sort(key=lambda result: result['date'])
            test['finished_students_results'] = results
            tests.append(test)
    context = {
        'title': 'Запущенные тесты',
        'tests': tests
    }
    return render(request, 'main/lecturer/runningTests.html', context)


@post_method
@unauthenticated_user
@allowed_users(allowed_roles=['lecturer'])
def stop_running_test(request):
    """
    Displays page with results of passing stopped test
    """
    test = Test.objects.get(id=int(request.POST['test_id']))
    storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
    test_results = storage.get_running_test_results(
        test_id=test.id,
        lecturer_id=request.user.id)
    storage.stop_running_test(
        test_id=test.id,
        lecturer_id=request.user.id)
    results = test_results['results']
    results.sort(key=lambda result: result['date'])
    context = {
        'title': 'Результаты тестирования',
        'test': test,
        'start_date': test_results['date'],
        'questions': json.dumps([result['questions'] for result in results]),
        'end_date': datetime.now() + timedelta(hours=3),
        'results': results,
    }
    return render(request, 'main/lecturer/testingResults.html', context)


@unauthenticated_user
@allowed_users(allowed_roles=['lecturer'])
def tests_results(request):
    """
    Displays page with all tests results
    """
    storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
    results = storage.get_all_tests_results()

    context = {
        'title': 'Результаты тестирований',
        'subjects': Subject.objects.all(),
        'lecturers': User.objects.filter(groups__name='lecturer'),
        'tests': Test.objects.all(),
        'results': json.dumps(results)
    }
    return render(request, 'main/lecturer/testsResults.html', context)


@unauthenticated_user
@allowed_users(allowed_roles=['lecturer'])
def show_test_results(request, test_result_id):
    """
    Displays page with testing results
    """
    storage = mongo.TestsResultsStorage.connect(db=mongo.get_conn())
    test_results = storage.get_test_result(_id=test_result_id)
    test = Test.objects.get(id=test_results['test_id'])
    results = test_results['results']
    results.sort(key=lambda result: result['date'])
    context = {
        'title': 'Результаты тестирования',
        'test': test,
        'start_date': test_results['date'],
        'questions': json.dumps([result['questions'] for result in results]),
        'results': results,
    }
    return render(request, 'main/lecturer/testingResults.html', context)


def get_left_time(request):
    """Return time that left for passing test"""
    if request.user.is_authenticated and request.method == 'POST':
        storage = mongo.RunningTestsAnswersStorage.connect(db=mongo.get_conn())
        left_time = storage.get_left_time(user_id=request.user.id)
        if left_time is not None:
            return JsonResponse(left_time, safe=False)
    return JsonResponse({}, safe=False)
