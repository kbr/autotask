from django.contrib import admin
from .models import TaskQueue


class TaskQueueAdmin(admin.ModelAdmin):
    list_display = ('module', 'function_name', 'is_periodic',
                    'scheduled', 'status')

    def function_name(self, obj):
        """
        Remove the tailing '_cron', '_periodic' or '_delayed" from the
        name, which is just used internal.
        """
        # shortcut: fn is the function_name
        fn = obj.function
        index = fn.rindex('_')
        if index > -1:
            fn = fn[:index]
        return fn


admin.site.register(TaskQueue, TaskQueueAdmin)
