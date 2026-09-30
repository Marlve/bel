# PromptBar's animation: the rejection shake (the one Tween it owns) plus
# the flight opacities, which are tick-fed the same way ChatCardAnimation's
# radius/tilt are - except here the ticks are pushed in from outside, by
# PromptFlow's clock via setFlight(), rather than from a Clock owned here.
# Moves the view (parent) directly during the shake, same as
# ChatCardAnimation.onFadeTick.

import math

import style
from util import LiveMotion
from anims.clock import Tween


class PromptBarAnimation(LiveMotion):
    def __init__(self, parent):
        self.parent = parent
        self.rect_opacity = 0.0  # the frame fades in as the wedge fades out
        self.chrome_opacity = 0.0  # the send hint follows, once the frame is at rest
        self.rest_x = 0

        # Rejected: the frame shakes in place, keeping whatever was typed.
        self.shake = Tween(parent, self.onShakeTick, self.onShakeDone)

    def reset(self):
        self.shake.stop()
        self.rect_opacity = 0.0
        self.chrome_opacity = 0.0

    def setFlight(self, rect_opacity, chrome_opacity):
        self.rect_opacity = rect_opacity
        self.chrome_opacity = chrome_opacity
        self.parent.update()

    def onShakeTick(self, t):
        offset = math.sin(t * 2 * math.pi * style.REJECT_SHAKES) * style.REJECT_SHIFT
        self.parent.move(round(self.rest_x + offset), self.parent.y())

    def onShakeDone(self):
        self.parent.move(self.rest_x, self.parent.y())
