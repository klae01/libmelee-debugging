"""Open API written in Python for making your own Smash Bros: Melee AI
Python3 only
Works on Linux/OSX/Windows
"""

import melee.version
from melee import framedata, menuhelper, stages, techskill
from melee.console import Console
from melee.controller import Controller, ControllerState
from melee.enums import *
from melee.framedata import FrameData
from melee.gamestate import GameState
from melee.logger import Logger
from melee.menuhelper import MenuHelper
