#Autotask

autotask is a **django-application** for handling asynchronous tasks without the need to install, configure and supervise additional processes (like celery, redis or rabbitmq). autotask is aimed for applications where asynchronous tasks happend occasionally and the installation, configuration and monitoring of an additionally technology stack seems to be to much overhead.


##Installation

Download and install using pip:

    pip install autotask

Register *autotask* as application in *settings.py*:

    # Application definition
    INSTALLED_APPS = [
        ...
        'autotask',
    ]

Run migrations to install the database-table used by *autotask*:

    $ python manage.py migrate


##Usage

autotask offers three decorators for handling asynchronous task:

    from autotask.tasks import (
        delayed_task,
        periodic_task,
        cron_task,
    )


###delayed_task

    @delayed_task(delay=0, retries=0, ttl=300)
    def some_function(*args, **kwargs):
        ...

A call to a function decorated by **@delayed_task()** will return immediately. The function itself will get executed later in another process. The decorator takes the following optional arguments:

- **delay**: time in seconds to wait at least befor the function gets executed. Defaults to 0 (as soon as possible).
- **entries**: Number of retries to execute a function in case of a failure. Defaults to 0 (no retries).
- **ttl**: time to live. After running a function the result will be stored at least for this time. Defaults to 300 seconds.

The decorated function returns an object with the following attributes:

**ready**: True if the task has been executed or False in case the task is still waiting for execution.

**status**: Can have the following values (which can be imported from autotask.task):

    from autotask.task import (
        WAITING,
        RUNNING,
        DONE,
        ERROR
    )

    - WAITING: tasks waits for execution
    - RUNNING: task gets executed right now
    - DONE: task has been executed
    - ERROR: an error has occured during the execution

**result**: the result of the executed task


###periodic_task

    @periodic_task(seconds=3600, start_now=False)
    def some_function(*args, **kwargs):
        ...

A function decorated by **@periodic_task()** should not get called but has to be imported when django starts up to execute the decorator. This will register the function to get executed periodically. The decorator takes the following optional arguments:

**seconds**: time in seconds to wait before executing the function again. Defaults to 3600 (an hour).

**start_now**: a boolean value: if *True* execute as soon as possible and then periodically. If *False* wait for the given number of seconds before running periodically. Defaults to *False*.


###cron_task

    @cron_task(minutes=None, hours=None, dow=None,
               months=None, dom=None, crontab=None)
    def some_function(*args, **kwargs):
        ...

A function decorated by **@cron_task()** should not get called but has to be imported when django starts up to execute the decorator. This will register the function to get executed according to the crontab-arguments. These arguments can  be given as python sequences or as a crontab-string.

**minutes**: list of minutes during an hour when the task should run. Valid entries are integers in the range 0-59. Defaults to None which is the same as '*' in a crontab, meaning that the tasks gets executed every minute.

**hours**: list of hours during a day when the task should run. Valid entries are integers in the range 0-23. Defaults to None which is the same as '*' in a crontab, meaning that the tasks gets executed every hour.

**dow**: days of week. A list of integers from 0 to 6 with Monday as 0. The task runs only on the given weekdays. Defaults to None which is the same as '*' in a crontab, meaning that the tasks gets executed every day of the week.

**months**: list of month during a year when the task should run. Valid entries are integers in the range 1-12. Defaults to None which is the same as '*' in a crontab, meaning that the tasks gets executed every month.

**dom**: list of days in an month the task should run. Valid entries are integers in the range 1-31. Defaults to None which is the same as '*' in a crontab, meaning that the tasks gets executed every day.

If neither **dom** nor **dow** are given, then the task should run every day of a month. If one of both are set, then the given restrictions apply. If both are set, then the allowed days are complement each other.

**crontab**: a string representing a valid crontab. See: [https://en.wikipedia.org/wiki/Cron#CRON_expression](https://en.wikipedia.org/wiki/Cron#CRON_expression) with the restriction that only integers and the special signs (* , -) are allowed. Some examples:

    - * * * * *: runs every minute
    - 15,30 7 * * *: runs every day at 7:15 and 7:30
    - * 9 0 4,7 10-15: runs at 9:00 every monday and from the 10th to the 15th of a month but only in April and July.

If the argument **crontab** is given all other arguments are ignored.


##Requirements

- Python >= 3.3, 2.7
- Django >= 1.8
- Database: PostgreSQL


##How does this work

For every django-process a corresponding worker-process gets started by autotask to handle delayed or periodic tasks.

The worker-process is monitored: if the worker terminates (for whatever reason) a restart will happen after a few seconds.

If the django-process terminates, the worker terminates also.
