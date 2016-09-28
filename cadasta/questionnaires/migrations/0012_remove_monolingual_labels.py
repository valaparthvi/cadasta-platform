# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-10-10 17:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaires', '0011_migrate_monolingual_labels'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalquestion',
            name='label',
        ),
        migrations.RemoveField(
            model_name='historicalquestiongroup',
            name='label',
        ),
        migrations.RemoveField(
            model_name='historicalquestionoption',
            name='label',
        ),
        migrations.RemoveField(
            model_name='question',
            name='label',
        ),
        migrations.RemoveField(
            model_name='questiongroup',
            name='label',
        ),
        migrations.RemoveField(
            model_name='questionoption',
            name='label',
        ),
    ]