"""Open API written in Python for making your own Smash Bros: Melee AI
Python3 only
Currently only works on Linux/OSX
"""

import melee.version
from melee.controller import Controller, ControllerState
from melee.dolphin import Dolphin
from melee.enums import Action, Button, Character, Menu, ProjectileSubtype, Stage
from melee.gamestate import GameState
from melee.logger import Logger
