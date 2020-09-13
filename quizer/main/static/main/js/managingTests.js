function getDivElement(test, staticPath, questionsRef) {
    const container = document.createElement('div');

    const hr = document.createElement('hr');
    hr.className = "my-4";

    const label = document.createElement('label');
    label.htmlFor = "test_name";

    const test_name_h3 = document.createElement('h3');
    test_name_h3.innerHTML = `${test.name}`;

    const descriptionP = document.createElement('p');
    descriptionP.innerHTML = `${test.description}`;

    const infoP = document.createElement('p');
    infoP.innerHTML = `<img src='${staticPath}main/images/subject.svg'> Предмет: ${test.subject.name}<br>
    <img src='${staticPath}main/images/research.svg'> Количество заданий в тесте: ${test.tasks_num}<br>
    <img src='${staticPath}main/images/clock.svg'> Время на выполнение: ${test.duration} с<br>
    <img src='${staticPath}main/images/database.svg'> Вопросов к тесту: ${test.questions_num}`;

    const btnCont1 = document.createElement('div');
    btnCont1.className = "btn-group mr-3";
    const btnCont2 = document.createElement('div');
    btnCont2.className = "btn-group mr-1";
    const btnCont3 = document.createElement('div');
    btnCont3.className = "btn-group mr-1";
    const btnCont4 = document.createElement('div');
    btnCont4.className = "btn-group mr-3";
    const btnCont5 = document.createElement('div');
    btnCont5.className = "btn-group mr-1";

    const editTestBtn = document.createElement('button');
    editTestBtn.className = "btn btn-primary js-open-modal";
    editTestBtn.innerHTML = `<img src='${staticPath}main/images/edit.svg'> Редактировать`;
    editTestBtn.setAttribute('data-modal', 'edit-modal');
    editTestBtn.setAttribute('onclick',
        `fillEditModal(${test.id}, "${test.name}", "${test.description}", "${test.tasks_num}", "${test.duration}")`);

    const qstnsRef = document.createElement('a');
    qstnsRef.className = "btn btn-success";
    qstnsRef.innerHTML = `<img src='${staticPath}main/images/white_database.svg'> Вопросы к тесту`;
    qstnsRef.href = questionsRef.replace(/test_id/gi, `${test.id}`)
    console.log(questionsRef);

    const addQstnBtn = document.createElement('button');
    addQstnBtn.className = "btn btn-success js-open-modal";
    addQstnBtn.innerHTML = `<img src='${staticPath}main/images/add.svg'> Добавить вопрос`;
    addQstnBtn.setAttribute('data-modal', 'add-question-modal');
    addQstnBtn.setAttribute('onclick', `fillAddQuestionModal(${test.id})`);

    const loadQstnBtn = document.createElement('button');
    loadQstnBtn.className = "btn btn-success js-open-modal";
    loadQstnBtn.innerHTML = `<img src='${staticPath}main/images/download.svg'> Загрузить вопросы`;
    loadQstnBtn.setAttribute('data-modal', 'load-questions-modal');
    loadQstnBtn.setAttribute('onclick', `fillLoadQuestionsModal(${test.id})`);

    const delTestBtn = document.createElement('button');
    delTestBtn.className = "btn btn-danger js-open-modal";
    delTestBtn.innerHTML = `<img src='${staticPath}main/images/delete.svg'> Удалить тест`;
    delTestBtn.setAttribute('data-modal', 'delete-modal');
    delTestBtn.setAttribute('onclick',
        `fillDeleteModal(${test.id}, "${test.name}")`);

    btnCont1.appendChild(editTestBtn);
    btnCont2.appendChild(qstnsRef);

    btnCont3.appendChild(addQstnBtn);
    btnCont4.appendChild(loadQstnBtn);

    btnCont5.appendChild(delTestBtn);

    label.appendChild(test_name_h3);
    label.appendChild(descriptionP);
    label.appendChild(infoP);
    label.appendChild(btnCont1);
    label.appendChild(btnCont2);
    label.appendChild(btnCont3);
    label.appendChild(btnCont4);
    label.appendChild(btnCont5);

    container.appendChild(hr);
    container.appendChild(label);

    return container;
}

function fillEditModal(testID, testName, testDescription, testTasksNum, testDuration) {
    const idInput = document.getElementById('edit-test-id');
    idInput.value = testID;

    const nameInput = document.getElementById('edit-test-name');
    nameInput.value = testName;

    const descriptionInput = document.getElementById('edit-test-description');
    descriptionInput.value = testDescription;

    const tasksNumInput = document.getElementById('edit-test-tasks-num');
    tasksNumInput.value = testTasksNum;

    const durationInput = document.getElementById('edit-test-duration');
    durationInput.value = testDuration;
}

function fillDeleteModal(testID, testName) {
    const deleteP = document.getElementById('delete-p');
    deleteP.innerHTML = `Вы действительно хотите удалить тест '${testName}'?<br>
 		                 Тогда все связанные с ним вопросы будут удалены.`;

    const deleteTestInput = document.getElementById('delete-test-id');
    deleteTestInput.value = testID;
}

function fillAddQuestionModal(testID) {
    const testIDInput = document.getElementById('add-question-test-id');
    testIDInput.value = testID;
}

function fillLoadQuestionsModal(testID) {
    const testIDInput = document.getElementById('load-questions-test-id');
    testIDInput.value = testID;
}

function main(testsUrl, staticPath, questionsRef) {
    const testsContainer = document.getElementById("tests_container");
    const subject = document.getElementById("subject");
    const nameFilter = document.getElementById("name_filter");

    let tests = [];
	$.get(testsUrl).done(function(response) {
        tests = response['tests'];
        for (let test of tests) {
            if (test.subject.id == subject.options[subject.selectedIndex].value) {
                testsContainer.appendChild(getDivElement(test, staticPath, questionsRef));
            }
        }
        activateModalWindows();
	});

    subject.onkeyup = subject.onchange = () =>  {
        testsContainer.innerHTML = '';
        for (let test of tests) {
            if (test.name.includes(nameFilter.value)) {
                if (test.subject.id == subject.options[subject.selectedIndex].value) {
                    testsContainer.appendChild(getDivElement(test, staticPath, questionsRef));
                }
            }
        }
        activateModalWindows();
    };

    nameFilter.onkeyup = nameFilter.onchange = () =>  {
        testsContainer.innerHTML = '';
        for (let test of tests) {
            if (test.name.includes(nameFilter.value)) {
                if (test.subject.id == subject.options[subject.selectedIndex].value) {
                    testsContainer.appendChild(getDivElement(test, staticPath, questionsRef));
                }
            }
        }
        activateModalWindows();
    };
}
