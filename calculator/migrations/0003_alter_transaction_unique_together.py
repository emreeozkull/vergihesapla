# Generated by Django 4.0.6 on 2025-02-21 07:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calculator', '0002_alter_transaction_price_alter_transaction_quantity_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='transaction',
            unique_together={('pdf', 'date', 'symbol', 'transaction_type', 'price', 'quantity')},
        ),
    ]
