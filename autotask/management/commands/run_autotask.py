"""
Entry-point for starting the workers.
"""

from django.core.management.base import BaseCommand
from autotask.worker import start_worker


class Command(BaseCommand):
    help = 'starts the autotask workers'

    def handle(self, *args, **options):
        start_worker()
