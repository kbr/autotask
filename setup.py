from setuptools import setup


def readme():
    with open('README.rst', 'r') as f:
        content = f.read()
    return content


setup(name='autotask',
      version='0.5.3',
      description='A django-application for handling asynchronous tasks.',
      long_description=readme(),
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
      ],
      keywords='django-application autotask asynchron',
      url='https://bitbucket.org/kbr/autotask',
      author='Klaus Bremer',
      author_email='bremer@bremer-media.de',
      license='MIT',
      packages=[
        'autotask',
        'autotask/management',
        'autotask/management/commands',
        'autotask/migrations',
        'autotask/test',
      ],
      zip_safe=False
)
