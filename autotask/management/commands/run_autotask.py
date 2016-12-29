"""
Entry-point for starting the workers.
"""

from django.core.management.base import BaseCommand
from autotask.workers import start_workers


class Command(BaseCommand):
    help = 'starts the autotask workers'

    def handle(self, *args, **options):
        start_workers()
