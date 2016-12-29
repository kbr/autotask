
from datetime import timedelta

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _


WAITING = 1
RUNNING = 2
DONE = 3
ERROR = 4

STATUS_CHOICES = (
    (WAITING, 'waiting'),
    (RUNNING, 'running'),
    (DONE, 'done'),
    (ERROR, 'error'),
)


@python_2_unicode_compatible
class TaskQueue(models.Model):

    scheduled = models.DateTimeField(
        _('scheduled'))

    module = models.CharField(
        _('Module Name'),
        max_length=256)

    function = models.CharField(
        _('Function Name'),
        max_length=256)

    arguments = models.BinaryField(
        _('Arguments'),
        blank=True)

    is_periodic = models.BooleanField(
        _('Is periodic task'),
        default=False)

    timedelta = models.DurationField(
        _('timedelta'),
        blank=True,
        null=True)

    cron_data = models.BinaryField(
        _('cron data'),
        blank=True)

    status = models.IntegerField(
        _('Status'),
        choices=STATUS_CHOICES,
        default=WAITING)

    retries = models.IntegerField(
        _('Retries'),
        default=0)

    result = models.BinaryField(
        _('Result'),
        blank=True)

    ttl = models.DurationField(
        _('time to live'),
        blank=True,
        null=True)

    expire = models.DateTimeField(
        _('expire'),
        blank=True,
        null=True)

    error_message = models.TextField(
        _('error message'),
        blank=True)

    class Meta:
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        task = 'cron' if self.is_periodic else 'task'
        info = '{}: {}'.format(task, self.function)
        return info

    def save(self, **kwargs):
        if not self.ttl:
            self.ttl = timedelta()
        if not self.timedelta:
            # prevent an uninitialized task from running mad
            self.timedelta = timedelta(seconds=3600)
        if not self.scheduled:
            # try to avoid zombies
            self.scheduled = now()
        super(TaskQueue, self).save(**kwargs)
