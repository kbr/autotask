Django-Autotask
===============

autotask is a django-application for handling asynchronous tasks without the need to install, configure and supervise additional processes like `celery <http://www.celeryproject.org/>`_, `redis <http://redis.io/>`_ or `rabbitmq <https://www.rabbitmq.com/>`_ . autotask is aimed for applications where asynchronous tasks happen occasionally and the installation, configuration and monitoring of an additionally technology stack seems to be to much overhead.

The Code is available on `bitbucket <https://bitbucket.org/kbr/autotask>`_ and can also installed with ::

    pip install autotask

Requirements: ::

    - Python >= 3.3, 2.7
    - Django >= 1.8
    - Databases: PostgreSQL, SQLite3
                (MySQL and Oracle should work, but untested)



Installation
------------

Download and install using pip ::

    pip install autotask

Then register *autotask* as application in *settings.py* ::

    # Application definition
    INSTALLED_APPS = [
        ...
        'autotask',
    ]

Run migrations to install the database-table used by *autotask* ::

    $ python manage.py migrate

Usage
-----

Activate *autotask* in *settings.py* ::

    AUTOTASK_IS_ACTIVE = True

Note: don't activate *autotask* before running *python manage.py migrate*. Otherwise *autotask* will try to access an undefined database-table.

*autotask* offers three decorators to handle asynchronous tasks ::

    from autotask.tasks import (
        delayed_task,
        periodic_task,
        cron_task,
    )

If *autotask* is not active the decorators will not return a wrapper but the original function. So the decorators will have no effect and the functions will behave as undecorated.


@delayed_task:
..............

::

    @delayed_task(delay=0, retries=0, ttl=300)
    def some_function(*args, **kwargs):
        ...

A call to a function decorated by *@delayed_task()* will return immediately. The function itself will get executed later in another process. The decorator takes the following optional arguments:

:delay: time in seconds to wait at least before the function gets executed. Defaults to 0 (as soon as possible).

:retries:
    Number of retries to execute a function in case of a failure. Defaults to 0 (no retries).

:ttl: time to live. After running a function the result will be stored at least for this time. Defaults to 300 seconds.

The decorated function returns an object with the following attributes:

:ready: True if the task has been executed or False in case the task is still waiting for execution.

:status:
    Can have the following values (which can be imported from autotask.task)

    ::

        from autotask.task import (
            WAITING,
            RUNNING,
            DONE,
            ERROR
        )

        - WAITING: task waits for execution
        - RUNNING: task gets executed right now
        - DONE: task has been executed
        - ERROR: an error has occured during the execution


:result: the result of the executed task.

:error_message: holds the error-message as a string, if an error has occured.

A typical usecase is sending emails triggered by a request: ::

    from autotask.tasks import delayed_task

    @delayed_task()
    def send_mail(receivers, message):
        # your implementation here ...

And somewhere else in your code: ::

    def handle_request(request):
        ...
        send_mail(receivers, message)
        ...
        return response

The call to *sendmail()* returns immediately sending the response without waiting for the mailserver doing the job. The mail itself gets send by the worker running in another process.
Other examples are image-processing or whatever may take some time and can get handled separately.


@periodic_task:
...............

::

    @periodic_task(seconds=3600, start_now=False)
    def some_function(*args, **kwargs):
        ...

A function decorated by *@periodic_task()* should not get called but has to be defined in a module that gets imported when django starts up to execute the decorator. This will register the function to get executed periodically. The decorator takes the following optional arguments:

:seconds:
    time in seconds to wait before executing the function again. Defaults to 3600 (an hour).

:start_now:
    a boolean value. True: execute as soon as possible and then periodically. False: wait for the given number of seconds before running periodically. Defaults to False.

A usecase here may be running some periodic clean-up: ::

    from autotask.tasks import periodic_task

    @periodic_task(seconds=600)
    def clean_up():
        queryset = MyModel.objects.filter(obsolete=True)
        queryset.delete()

The function *clean_up()* must not get called from your program. Instead the module where the function is defined has to get imported when django starts up. This is because decorators are executed during module-import and this way the function *clean_up* gets registered by autotask to get called every ten minutes.


@cron_task:
...........

::

    @cron_task(minutes=None, hours=None, dow=None,
               months=None, dom=None, crontab=None)
    def some_function(*args, **kwargs):
        ...

A function decorated by *@cron_task()* should not get called but has to be defined in a module that gets imported when django starts up to execute the decorator. This will register the function to get executed according to the crontab-arguments. These arguments can be given as python sequences by keyword-parameters or as a crontab-string.

:minutes:
    list of minutes during an hour when the task should run. Valid entries are integers in the range 0-59. Defaults to None which is the same as '*' in a crontab, meaning that the task gets executed every minute.

:hours:
    list of hours during a day when the task should run. Valid entries are integers in the range 0-23. Defaults to None which is the same as '*' in a crontab, meaning that the task gets executed every hour.

:dow:
    days of week. A list of integers from 0 to 6 with Monday as 0. The task runs only on the given weekdays. Defaults to None which is the same as '*' in a crontab, meaning that the task gets executed every day of the week.

:months:
    list of month during a year when the task should run. Valid entries are integers in the range 1-12. Defaults to None which is the same as '*' in a crontab, meaning that the task gets executed every month.

:dom:
    list of days in an month the task should run. Valid entries are integers in the range 1-31. Defaults to None which is the same as '*' in a crontab, meaning that the task gets executed every day.

If neither *dom* nor *dow* are given, then the task will run every day of a month. If one of both is set, then the given restrictions apply. If both are set, then the allowed days complement each other.

:crontab:
    a string representing a valid crontab. See: `https://en.wikipedia.org/wiki/Cron#CRON_expression <https://en.wikipedia.org/wiki/Cron#CRON_expression>`_ with the restriction that only integers and the special signs (* , -) are allowed. Some examples ::

        The order of arguments is:
        'minutes hours dow months dom'

        '* * * * *':       runs every minute
                           (same as @periodic_task(seconds=60))
        '15,30 7 * * *':   runs every day at 7:15 and 7:30
        '* 9 0 4,7 10-15': runs at 9:00 every monday and
                           from the 10th to the 15th of a month
                           but only in April and July.

If the argument *crontab* is given all other arguments are ignored.
On using *@cron_task* it is recommended to also install `pytz <http://pytz.sourceforge.net/>`_ .

An example for @cron_task may be sending a newsletter: ::

    from autotask.tasks import cron_task

    @cron_task(crontab="30 7 0 * *")
    def send_newsletter():
        # your implementation here

Like the @periodic_task decorator this function gets not called from the program but has to be imported at starting django. The function *send_newsletter* will then get executed every monday at 7:30 am.

Instead using the crontab-parameter as string the scheduling information can also given to the decorator using keyword-parameters: ::

    @cron_task(minutes=[30], hours=[7], dow=[0])
    def send_newsletter():
        # your implementation here


Settings
--------

All settings are optional and preset with default values. To override these defaults redefine them in the *settings.py* file.

**AUTOTASK_IS_ACTIVE**: Boolean. If *True* autotask will start a worker-process to handle the decorated tasks. Defaults to *False* (for easiers installation).

**AUTOTASK_WORKER_EXECUTABLE**: String. Path to the executable for *manage.py <command>*. Must be absolute or relative to the working directory defined by BASE_DIR in the *settings.py* file. Defaults to "python" without a leading path.

**AUTOTASK_WORKER_MONITOR_INTERVALL**: Integer. Time in seconds for autotask to check whether the worker process is alive. Defaults to 5.

**AUTOTASK_HANDLE_TASK_IDLE_TIME**: Integer. Time in seconds to sleep on idle times. After processing a task autotask checks for the next task and executes it without delay if its scheduled for the current time. If no scheduled task is found autotasks sleeps for the given time in seconds. Defaults to 10.

**AUTOTASK_RETRY_DELAY**: Integer. Time in seconds autotask waits before executing a *@delayed_task* again in case an error has occured. Errors are unhandled exeptions. Defaults to 2.

**AUTOTASK_CLEAN_INTERVALL**: Integer. Time in seconds between database cleanup runs. After running a *@delayed_task* the result is stored for at least the given time to live (the decorator *ttl* parameter). After this period the entry will get removed by the next cleanup run to prevent the accumulation of outdated tasks in the database. Defaults to 600.


How does this work
------------------

For every django-process a corresponding worker-process gets started by autotask to handle delayed or periodic tasks.
The worker-process is monitored: if the worker terminates (for whatever reason) a restart will happen after a few seconds.
If the django-process terminates, the worker terminates also.

Handling a lot of delayed tasks can add an additional load to the database. It depends on the application whether this may be an issue.

It is not the intention of autotask to invoke the workers as fast as possible on incoming tasks but to delegate time consuming and periodic jobs.



Releases
--------

0.5.3
.....

Bugfix: missing import added.
Some typos in admin interface.

0.5.2
.....

Timezone bugfix

further release-history in RELEASES.rst
