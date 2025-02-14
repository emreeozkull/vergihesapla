# Generated by Django 4.0.6 on 2025-02-14 22:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calculator', '0004_remove_calculatorpdf_account_info_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='calculator',
            name='account_opening_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='calculator',
            name='customer_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='calculator',
            name='tckn',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
