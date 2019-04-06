# Generated by Django 2.1.6 on 2019-04-06 09:05

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Graph',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('graph_str', models.TextField()),
                ('ctime', models.DateTimeField(verbose_name='creation time')),
                ('mtime', models.DateTimeField(verbose_name='modification time')),
            ],
        ),
    ]
