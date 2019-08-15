from setuptools import setup

setup(name='minibot_server',
      version='0.1',
      packages=['minibot_server'],
      install_requires=[
        "tornado>=6.0",
        "PyYAML>=5.0",
        "attrs>=19.1",
      ],
      entry_points={
          'console_scripts': [
              'run_minibot_server=minibot_server:main',
              'run_twitch_irc_test=minibot_server.irc:TestTwitchIrcMain',
          ]
      })