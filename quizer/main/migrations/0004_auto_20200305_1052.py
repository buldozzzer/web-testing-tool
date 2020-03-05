# Generated by Django 2.2.10 on 2020-03-05 10:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_test_task_num'),
    ]

    operations = [
        migrations.RenameField(
            model_name='test',
            old_name='task_num',
            new_name='tasks_num',
        ),
        migrations.AlterField(
            model_name='task',
            name='task',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Test', verbose_name='Тест'),
        ),
    ]