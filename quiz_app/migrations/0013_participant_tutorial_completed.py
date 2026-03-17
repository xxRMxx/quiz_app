from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quiz_app', '0012_alter_category_options_alter_participant_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='tutorial_completed',
            field=models.BooleanField(default=False),
        ),
    ]
