# pylint: disable=import-error, invalid-name, too-few-public-methods, relative-beyond-top-level
"""
Main app tests, covered views.py and models.py.
Tests should be started using manage.py, because at the same time MONGO_DBNAME
value is replaced with 'test_${MONGO_DBNAME}' in config.py during the test run
"""
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from .models import Subject, Test, TestsResultsStorage, RunningTestsAnswersStorage, QuestionsStorage
from .config import MONGO_HOST, MONGO_PORT, MONGO_DBNAME


class MainTest(TestCase):
    """
    Base class for all tests
    """

    def setUp(self) -> None:
        """
        Add objects to temporary test 'test_${MONGO_DBNAME} database:
        - groups 'lecturer' and 'student'
        - 'lecturer' user and 'student' user
        - study subject 'Subject'
        - Subject 'Subject' test 'Hard test'
        - 2 questions for 'Hard test'
        """
        self.lecturer = User.objects.create_user(
            username='lecturer',
            password='top_secret'
        )
        Group.objects.create(
            id=1,
            name="lecturer"
        )
        self.lecturer.groups.add(1)

        self.student = User.objects.create_user(
            username='user',
            password='top_secret'
        )
        Group.objects.create(
            id=2,
            name="student"
        )
        self.student.groups.add(2)

        self.subject = Subject.objects.create(
            lecturer=self.lecturer,
            name='Subject',
            description='Description of subject'
        )
        self.test = Test.objects.create(
            subject=self.subject,
            author=self.lecturer,
            name='Hard test',
            description='Description of hard test for Subject',
            tasks_num=2,
            duration=60
        )

        self.questions_storage = QuestionsStorage.connect_to_mongodb(
            host=MONGO_HOST,
            port=MONGO_PORT,
            db_name=MONGO_DBNAME
        )
        self.running_tests_answers_storage = RunningTestsAnswersStorage.connect_to_mongodb(
            host=MONGO_HOST,
            port=MONGO_PORT,
            db_name=MONGO_DBNAME
        )
        self.tests_results_storage = TestsResultsStorage.connect_to_mongodb(
            host=MONGO_HOST,
            port=MONGO_PORT,
            db_name=MONGO_DBNAME
        )

        self.questions_storage.add_one(
            question={
                'formulation': 'First question with multiselect',
                'tasks_num': 3,
                'multiselect': True,
                'with_images': False,
                'options': [
                    {
                        'option': 'First true option',
                        'is_true': True
                    },
                    {
                        'option': 'Second false option',
                        'is_true': False
                    },
                    {
                        'option': 'Third true option',
                        'is_true': True
                    }
                ]
            },
            test_id=self.test.id
        )
        self.questions_storage.add_one(
            question={
                'formulation': 'Second question with single answer',
                'tasks_num': 2,
                'multiselect': False,
                'with_images': False,
                'options': [
                    {
                        'option': 'False option',
                        'is_true': False
                    },
                    {
                        'option': 'True option',
                        'is_true': True
                    },
                ]
            },
            test_id=self.test.id
        )


class QuestionsStorageTest(MainTest):
    """
    Tests for QuestionsStorage class which provides work
    with 'questions' collection in database
    """

    def test_adding_and_getting_questions(self) -> None:
        """
        Test for 'add_one' and 'get_many' QuestionsStorage methods
        """
        questions = self.questions_storage.get_many(test_id=self.test.id)
        question = {
            'formulation': 'Test question',
            'tasks_num': 2,
            'multiselect': False,
            'with_images': False,
            'options': [
                {
                    'option': 'First true option',
                    'is_true': True
                },
                {
                    'option': 'Second false option',
                    'is_true': False
                }
            ]
        }
        self.questions_storage.add_one(
            question=question,
            test_id=self.test.id
        )
        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(updated_questions, questions + [question])

    def test_deleting_questions(self) -> None:
        """
        Test for 'delete_one' and 'get_many' QuestionsStorage methods
        """
        questions = self.questions_storage.get_many(test_id=self.test.id)
        self.questions_storage.delete_one(
            question_formulation='First question with multiselect',
            test_id=self.test.id
        )
        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(len(questions) - 1, len(updated_questions))

    def test_deleting_all_questions(self) -> None:
        """
        Test for 'delete_many' and 'get_many' QuestionsStorage methods
        """
        questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertNotEqual(0, len(questions))

        self.questions_storage.delete_many(
            test_id=self.test.id
        )
        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(0, len(updated_questions))


class AuthorizationTest(MainTest):
    """
    Tests for authorization system in the application
    """

    def test_student_auth(self) -> None:
        """
        Test for authorization of user belonging to 'student' group
        """
        client = Client()
        client.logout()
        response = client.post(reverse('main:index'), {
            'username': self.student.username,
            'password': 'top_secret'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Пользователь')

    def test_lecturer_auth(self) -> None:
        """
        Test for authorization of user belonging to 'lecturer' group
        """
        client = Client()
        client.logout()
        response = client.post(reverse('main:index'), {
            'username': self.lecturer.username,
            'password': 'top_secret'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Преподаватель')

    def test_anonymous_auth(self) -> None:
        """
        Test for authorization of a user not registered in the system
        """
        client = Client()
        client.logout()
        response = client.post(reverse('main:index'), {
            'username': 'anonymous',
            'password': 'anonymous'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ошибка: неправильное имя пользователя или пароль!')

    def test_anonymous_redirect(self) -> None:
        """
        Test redirecting a logged-out user to the login page when trying to get to the home page
        """
        client = Client()
        client.logout()
        response = client.get(reverse('main:tests'), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Зайти в систему')


class AccessRightsTest(MainTest):
    """
    Testing access rights of various user groups
    """

    def test_student_access(self) -> None:
        """
        Testing that user belonging to 'student' group does not
        have permission to view 'lecturer' pages
        """
        client = Client()
        client.login(
            username=self.student.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {
            'username': self.student.username,
            'password': 'top_secret'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not permitted to see this page.')

    def test_lecturer_access(self) -> None:
        """
        Testing that user belonging to 'lecturer' group does not
        have permission to view 'student' pages
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:marks'), {
            'username': self.lecturer.username,
            'password': 'top_secret'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not permitted to see this page.')


class TestAddingTest(MainTest):
    """
    Tests adding tests using web interface
    """

    def test_student_has_no_access(self) -> None:
        """
        Testing, that student is not permitted
        to add new tests using web interface
         """
        client = Client()
        client.login(
            username=self.student.username,
            password='top_secret'
        )
        response = client.post(reverse('main:add_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not permitted to see this page.')

    def test_adding_new_test(self) -> None:
        """
        Testing adding new test by using web interface
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:add_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Новый тест')

        self.assertEqual(len(Test.objects.all()), 1)
        response = client.post(reverse('main:add_test_result'), {
            'subject': self.subject.name,
            'test_name': 'Second test',
            'description': 'Description of second test',
            'tasks_num': 3,
            'duration': 45
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        message = "Тест '%s' по предмету '%s' успешно добавлен." % ('Second test', self.subject.name)
        self.assertContains(response, message)
        self.assertEqual(len(Test.objects.all()), 2)


class TestEditingTest(MainTest):
    """
    Tests editing tests using web interface
    """

    def test_student_has_no_access(self) -> None:
        """
        Testing, that student is not permitted
        to edit tests using web interface
         """
        client = Client()
        client.login(
            username=self.student.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not permitted to see this page.')

    def test_editing_test(self) -> None:
        """
        Testing editing test by using web interface
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные тесты')

        old_test = Test.objects.get(id=self.test.id)

        response = client.post(reverse('main:edit_test_redirect'), {
            'test_name': self.test.name,
            'btn': 'edit_test_btn'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Окно редактирования теста')
        self.assertContains(response, self.test.name)

        updated_description = 'Updated description'
        response = client.post(reverse('main:edit_test_result'), {
            'test_id': self.test.id,
            'test_name': self.test.name,
            'description': updated_description,
            'tasks_num': self.test.tasks_num,
            'duration': self.test.duration
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, old_test.name)
        self.assertContains(response, "успешно изменен.")

        updated_test = Test.objects.get(id=self.test.id)

        self.assertNotEqual(old_test.description, updated_test.description)
        self.assertEqual(updated_test.description, updated_description)

    def test_deleting_test(self) -> None:
        """
        Testing deleting test using web interface
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные тесты')

        response = client.post(reverse('main:edit_test_redirect'), {
            'test_name': self.test.name,
            'btn': 'del_test_btn'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вы действительно хотите удалить тест")

        response = client.post(reverse('main:delete_test_result'), {
            'test_id': self.test.id,
            'del': 'on'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Результат удаления')
        self.assertContains(response, self.test.name)

        self.assertEqual(len(Test.objects.filter(id=self.test.id)), 0)

    def test_deleting_test_questions(self) -> None:
        """
        Testing deleting all test's questions using web interface
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные тесты')

        response = client.post(reverse('main:edit_test_redirect'), {
            'test_name': self.test.name,
            'btn': 'del_qstn_btn'
        }, follow=True)

        questions = self.questions_storage.get_many(test_id=self.test.id)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вопросы к тесту")
        self.assertContains(response, self.test.name)

        response = client.post(reverse('main:delete_questions_result'), {
            'test_id': self.test.id,
            'csrfmiddlewaretoken': 'token',
            **{question['formulation']: 'on' for question in questions}
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Результат удаления')
        self.assertContains(response, self.test.name)

        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(len(updated_questions), 0)
        self.assertNotEqual(len(updated_questions), len(questions))


class LoadingQuestionsTest(MainTest):
    """
    Tests loading new questions from file using web interface
    """

    def test_loading_questions(self) -> None:
        """
        Testing adding new questions by loading them from file
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные тесты')

        response = client.post(reverse('main:edit_test_redirect'), {
            'test_name': self.test.name,
            'btn': 'load_qstn_btn'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Загрузить вопросы')

        old_questions = self.questions_storage.get_many(test_id=self.test.id)

        file_data = """Как создать вопрос?
+ добавив верные ответы
+ которых может быть несколько
- и есть неверные
- обеспечивается случайный порядок вопросов и ответов

Как создать вопрос со множественным выбором, но одним ответом?
* правильный вопрос выделить звездочкой
- а остальные ответы
- всё ещё с минусами
"""
        with open('tmp.txt', 'w') as file:
            file.write(file_data)

        with open('tmp.txt', 'r+') as file:
            response = client.post(reverse('main:load_questions_result'), {
                'test': self.test.name,
                'file': file
            }, follow=True)

        os.remove(file.name)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Новые вопросы')
        self.assertContains(response, self.test.name)

        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(len(updated_questions), len(old_questions) + 2)


class AddQuestionTest(MainTest):
    """
    Tests adding new questions using web interface
    """

    def test_adding_question(self) -> None:
        """
        Testing adding new questions by using web interface,
        testing 'add_one' and 'get_many' QuestionsStorage methods
        """
        client = Client()
        client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = client.post(reverse('main:edit_test'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные тесты')

        response = client.post(reverse('main:edit_test_redirect'), {
            'test_name': self.test.name,
            'btn': 'add_qstn_btn'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Новый вопрос')

        old_questions = self.questions_storage.get_many(test_id=self.test.id)
        response = client.post(reverse('main:add_question_result'), {
            'test': self.test.name,
            'question': 'New hard question',
            'tasks_num': 3,
            'multiselect': True,
            'option_1': 'False option',
            'option_2': 'True option!',
            'is_true_2': ['on'],
            'option_3': 'Another true option',
            'is_true_3': ['on']
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'успешно добавлен')
        updated_questions = self.questions_storage.get_many(test_id=self.test.id)
        self.assertEqual(len(updated_questions), len(old_questions) + 1)


class TestsResultsStorageTest(MainTest):
    """
    Tests for TestsResultsStorage class which stored all tests
    and their results in 'tests_results' collection in database,
    tests for running new test and stopping it using web interface
    """

    def setUp(self) -> None:
        """
        Runs new test by sending post request to '/run_test_result/' page
        """
        super().setUp()
        self.client = Client()
        self.client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        self.response = self.client.post(reverse('main:run_test_result'), {
            'test_name': self.test.name,
        }, follow=True)
        self.assertEqual(len(Test.objects.all()), 1)
        self.assertEqual(len(self.tests_results_storage.get_running_tests_ids()), 1)

    def test_running_new_test(self) -> None:
        """
        Testing running new test and stopping it using web interface,
        testing  'add_running_test', 'get_running_tests_ids' and
        'stop_running_test' TestsResultsStorage methods
        """
        self.assertEqual(self.response.status_code, 200)
        self.assertContains(self.response, 'Тест запущен')

        response = self.client.post(reverse('main:tests'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.test.name)

        response = self.client.post(reverse('main:stop_running_test'), {
            'test_name': self.test.name,
        }, follow=True)
        self.assertContains(response, self.test.name)
        self.assertEqual(0, len(self.tests_results_storage.get_running_tests_ids()))

    def test_running_tests_student_page(self) -> None:
        """
        Testing running new test and stopping it using web interface,
        testing 'student' '/tests' page,
        testing  'add_running_test', 'get_running_tests_ids' and
        'stop_running_test' TestsResultsStorage methods
        """
        self.client.logout()
        self.client.login(
            username=self.student.username,
            password='top_secret'
        )
        response = self.client.post(reverse('main:tests'), {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test.name)

        self.client.logout()
        self.client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = self.client.post(reverse('main:stop_running_test'), {
            'test_name': self.test.name,
        }, follow=True)
        self.assertContains(response, self.test.name)
        self.assertEqual(0, len(self.tests_results_storage.get_running_tests_ids()))

    def test_running_tests_lecturer_page(self) -> None:
        """
        Testing running new test and stopping it using web interface,
        testing 'lecturer' '/running_tests' page,
        testing  'add_running_test', 'get_running_tests_ids' and
        'stop_running_test' TestsResultsStorage methods
        """
        response = self.client.post(reverse('main:running_tests'), {}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test.name)

        response = self.client.post(reverse('main:stop_running_test'), {
            'test_name': self.test.name,
        }, follow=True)
        self.assertContains(response, self.test.name)
        self.assertEqual(0, len(self.tests_results_storage.get_running_tests_ids()))


class RunningTestsAnswersStorageTest(TestsResultsStorageTest):
    """
    Extends tests of the TestsResultsStorageTest class -
    testing the passage of tests by 'student',
    tests for RunningTestsAnswersStorage which temporary stores
    true answers for test passing by 'student'
    """

    def test_student_running_test_page(self) -> None:
        """
        Tests for passing running test by 'student' and getting
        its result by 'student' and 'lecturer' using web interface
        """
        client = Client()
        client.login(
            username=self.student.username,
            password='top_secret'
        )
        response = client.post(reverse('main:run_test'), {
            'test_name': self.test.name
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        right_answers = self.running_tests_answers_storage.get(
            user_id=self.student.id
        ).get('right_answers')
        self.assertEqual(len(right_answers), self.test.tasks_num)

        answers = {}
        for question_num in right_answers:
            if len(right_answers[question_num]['right_answers']) == 1:
                answers[question_num] = right_answers[question_num]['right_answers'][0]
            else:
                key = f'{question_num}_{right_answers[question_num]}'
                answers[key] = 'on'

        response = client.post(reverse('main:test_result'), {
            'time': self.test.duration // 2,
            'csrfmiddlewaretoken': 'token',
            **answers
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Результат')

        right_answers = self.running_tests_answers_storage.get(user_id=self.student.id)
        self.assertEqual(right_answers, None)

        self.client.logout()
        self.client.login(
            username=self.lecturer.username,
            password='top_secret'
        )
        response = self.client.post(reverse('main:stop_running_test'), {
            'test_name': self.test.name,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Результаты тестирования')
        self.assertContains(response, 'Тест: %s' % self.test.name)
        self.assertContains(response, self.student.username)
        self.assertEqual(0, len(self.tests_results_storage.get_running_tests_ids()))

        latest_test_results = self.tests_results_storage.get_latest_test_results(
            lecturer_id=self.lecturer.id,
            test_id=self.test.id
        )

        self.assertEqual(len(latest_test_results), 1)
        self.assertEqual(latest_test_results[0]['username'], self.student.username)
