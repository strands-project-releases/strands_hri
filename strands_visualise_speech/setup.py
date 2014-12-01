#!/usr/bin/env python

from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

d = generate_distutils_setup(
   #  don't do this unless you want a globally visible script
   # scripts=['bin/myscript'],
   packages=['peak_detect','pulseaudio'],
   package_dir={'peak_detect': 'src/sound_to_lights/contrib/peak_detect', 'pulseaudio': 'src/sound_to_lights/contrib/pulse/pulseaudio'}
)

setup(**d)
