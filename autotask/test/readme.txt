Tests are written for using pytest with pytest-django:
http://pytest.org/latest/index.html
https://pytest-django.readthedocs.org/en/latest/


pytest expects a 'pytest.ini' (or 'tox.ini') file in the project-directory
with the following content:

[pytest]
DJANGO_SETTINGS_MODULE = <your_project>.settings


On using django-configurations also add the configuration class:
https://django-configurations.readthedocs.org/en/stable/

DJANGO_CONFIGURATION = <the_configuration_class>
