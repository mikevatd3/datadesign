# Generated by Django 4.2.5 on 2023-09-23 19:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("smartcharts", "0004_remove_statlist_geo_compare_statlist_stat_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="datapoint",
            name="display_name",
            field=models.CharField(default="", max_length=256),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="statlist",
            name="stat_type",
            field=models.CharField(
                choices=[
                    ("VAL", "Number"),
                    ("PCT", "Percentage"),
                    ("DLR", "Dollar"),
                    ("COU", "Count"),
                ],
                max_length=3,
            ),
        ),
    ]