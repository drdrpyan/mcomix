# -*- coding: utf-8 -*-

""" Dynamic hotkey management

This module handles global hotkeys that were previously hardcoded in events.py.
All menu accelerators are handled using GTK's built-in accelerator map. The map
doesn't seem to support multiple keybindings for one action, though, so this
module takes care of the problem.

At runtime, other modules can register a callback for a specific action name.
This action name has to be registered in BINDING_INFO, or an Exception will be
thrown. The module can pass a list of default keybindings. If the user hasn't
configured different bindings, the default ones will be used.

Afterwards, the action will be stored together with its keycode/modifier in a
dictionary:
(keycode: int, modifier: GdkModifierType) =>
    (action: string, callback: func, args: list, kwargs: dict)

Default keybindings will be stored here at initialization:
action-name: string => [keycodes: list]


Each action_name can have multiple keybindings.
"""

import gtk
import json
from collections import defaultdict

from mcomix import constants
from mcomix import log

#: Bindings defined in this dictionary will appear in the configuration dialog.
#: If 'group' is None, the binding cannot be modified from the preferences dialog.
BINDING_INFO = {
    'previous page' : { 'title' : _('Previous page'), 'group' : _('Reading') },
    'next page' : { 'title' : _('Next page'), 'group' : _('Reading') },
    'previous page ff' : { 'title': _('Back ten pages'), 'group': _('Reading') },
    'next page ff' : { 'title': _('Forward ten pages'), 'group': _('Reading') },
    'previous page dynamic' : { 'title': _('Previous page (dynamic)'), 'group': _('Reading') },
    'next page dynamic' : { 'title': _('Next page (dynamic)'), 'group': _('Reading') },

    'scroll left bottom' : { 'title' : _('Scroll to bottom left'), 'group' : _('Page orientation and zoom')},
    'scroll middle bottom' : { 'title' : _('Scroll to bottom center'), 'group' : _('Page orientation and zoom')},
    'scroll right bottom' : { 'title' : _('Scroll to bottom right'), 'group' : _('Page orientation and zoom')},

    'scroll left middle' : { 'title' : _('Scroll to middle left'), 'group' : _('Page orientation and zoom')},
    'scroll middle' : { 'title' : _('Scroll to center'), 'group' : _('Page orientation and zoom')},
    'scroll right middle' : { 'title' : _('Scroll to middle right'), 'group' : _('Page orientation and zoom')},

    'scroll left top' : { 'title' : _('Scroll to top left'), 'group' : _('Page orientation and zoom')},
    'scroll middle top' : { 'title' : _('Scroll to top center'), 'group' : _('Page orientation and zoom')},
    'scroll right top' : { 'title' : _('Scroll to top right'), 'group' : _('Page orientation and zoom')},

    'exit fullscreen' : { 'title' : _('Exit from fullscreen'), 'group' : _('User interface')},
    'toggle fullscreen' : { 'title' : _('Toggle fullscreen'), 'group' : _('User interface')},

    'zoom in' : { 'title' : _('Zoom in'), 'group' : _('Page orientation and zoom')},
    'zoom out' : { 'title' : _('Zoom out'), 'group' : _('Page orientation and zoom')},
    'zoom original' : { 'title' : _('Normal size'), 'group' : _('Page orientation and zoom')},

    'scroll down' : { 'title' : _('Scroll down'), 'group' : _('Reading') },
    'scroll up' : { 'title' : _('Scroll up'), 'group' : _('Reading') },
    'scroll right' : { 'title' : _('Scroll right'), 'group' : _('Reading') },
    'scroll left' : { 'title' : _('Scroll left'), 'group' : _('Reading') },

    'smart scroll up' : { 'title' : _('Smart scroll up'), 'group' : _('Reading') },
    'smart scroll down' : { 'title' : _('Smart scroll down'), 'group' : _('Reading') },

    'osd panel' : { 'title' : _('Show OSD panel'), 'group' : _('User interface') },
}

# Generate 9 entries for executing command 1 to 9
for i in range(1, 10):
    BINDING_INFO['execute command %d' %i] = { 'title' : _('Execute external command') + u' (%d)' % i , 'group' : _('User interface') }


class _KeybindingManager(object):
    def __init__(self, window):
        #: Main window instance
        self._window = window

        self._action_to_callback = {} # action name => (func, args, kwargs)
        self._action_to_bindings = defaultdict(list) # action name => [ (key code, key modifier), ]
        self._binding_to_action = {} # (key code, key modifier) => action name

        self._initialize()

    def register(self, name, bindings, callback, args=[], kwargs={}):
        """ Registers an action for a predefined keybinding name.
        @param name: Action name, defined in L{BINDING_INFO}.
        @param bindings: List of keybinding strings, as understood
                         by L{gtk.accelerator_parse}. Only used if no
                         bindings were loaded for this action.
        @param callback: Function callback
        @param args: List of arguments to pass to the callback
        @param kwargs: List of keyword arguments to pass to the callback.
        """
        global BINDING_INFO
        assert name in BINDING_INFO, "'%s' isn't a valid keyboard action." % name

        # Load stored keybindings, or fall back to passed arguments
        keycodes = self._action_to_bindings[name]
        if keycodes == []:
            keycodes = [gtk.accelerator_parse(binding) for binding in bindings ]

        for keycode in keycodes:
            if keycode in self._binding_to_action.keys():
                if self._binding_to_action[keycode] != name:
                    log.warning(_('Keybinding for "%(action)s" overrides hotkey for another action.'),
                            {"action": name})
                    log.warning('Binding %s overrides %r' % (keycode, self._binding_to_action[keycode]))
            else:
                self._binding_to_action[keycode] = name
                self._action_to_bindings[name].append(keycode)

        self._action_to_callback[name] = (callback, args, kwargs)

    def edit_accel(self, name, new_binding, old_binding):
        """ Changes binding for an action
        @param name: Action name
        @param new_binding: Binding to be assigned to action
        @param old_binding: Binding to be removed from action [ can be empty: "" ]

        @return None: new_binding wasn't in any action
                action name: where new_binding was before
        """
        global BINDING_INFO
        assert name in BINDING_INFO, "'%s' isn't a valid keyboard action." % name

        nb = gtk.accelerator_parse(new_binding)
        old_action_with_nb = self._binding_to_action.get(nb)
        if old_action_with_nb is not None:
            self._binding_to_action.pop(nb)  # erase old binding with nb
            self._action_to_bindings[old_action_with_nb].remove(nb)

        if old_binding != "":
            ob = gtk.accelerator_parse(old_binding)

            self._binding_to_action.pop(ob)
            self._binding_to_action[nb] = name

            idx = self._action_to_bindings[name].index(ob)
            self._action_to_bindings[name].pop(idx)
            self._action_to_bindings[name].insert(idx, nb)
        else:
            self._binding_to_action[nb] = name
            self._action_to_bindings[name].append(nb)

        self.save()
        return old_action_with_nb

    def clear_accel(self, name, binding):
        """ Remove binding for an action """
        global BINDING_INFO
        assert name in BINDING_INFO, "'%s' isn't a valid keyboard action." % name

        ob = gtk.accelerator_parse(binding)
        self._action_to_bindings[name].remove(ob)
        self._binding_to_action.pop(ob)

        self.save()

    def execute(self, keybinding):
        """ Executes an action that has been registered for the
        passed keyboard event. If no action is bound to the passed key, this
        method is a no-op. """
        if keybinding in self._binding_to_action:
            action = self._binding_to_action[keybinding]
            func, args, kwargs = self._action_to_callback[action]
            self._window.emit_stop_by_name('key_press_event')
            return func(*args, **kwargs)

        # Some keys enable additional modifiers (NumLock enables GDK_MOD2_MASK),
        # which prevent direct lookup simply by being pressed.
        # XXX: Looking up by key/modifier probably isn't the best implementation
        for stored_binding, action in self._binding_to_action.iteritems():
            stored_keycode, stored_flags = stored_binding
            if stored_keycode == keybinding[0] and stored_flags & keybinding[1]:
                func, args, kwargs = self._action_to_callback[action]
                self._window.emit_stop_by_name('key_press_event')
                return func(*args, **kwargs)

        # Some keys may need modifiers to be typeable, but may be registered without.
        if (keybinding[0], 0) in self._binding_to_action:
            action = self._binding_to_action[(keybinding[0], 0)]
            func, args, kwargs = self._action_to_callback[action]
            self._window.emit_stop_by_name('key_press_event')
            return func(*args, **kwargs)


    def save(self):
        """ Stores the keybindings that have been set to disk. """
        # Collect keybindings for all registered actions
        action_to_keys = {}
        for action, bindings in self._action_to_bindings.iteritems():
            if bindings is not None:
                action_to_keys[action] = [
                    gtk.accelerator_name(keyval, modifiers) for
                    (keyval, modifiers) in bindings
                ]
        fp = file(constants.KEYBINDINGS_CONF_PATH, "w")
        json.dump(action_to_keys, fp, indent=2)
        fp.close()

    def _initialize(self):
        """ Restore keybindings from disk. """
        try:
            fp = file(constants.KEYBINDINGS_CONF_PATH, "r")
            stored_action_bindings = json.load(fp)
            fp.close()
        except Exception, e:
            log.error(_("Couldn't load keybindings: %s"), e)
            stored_action_bindings = {}

        for action in BINDING_INFO.iterkeys():
            if action in stored_action_bindings:
                bindings = [
                    gtk.accelerator_parse(keyname)
                    for keyname in stored_action_bindings[action] ]
                self._action_to_bindings[action] = bindings
                for binding in bindings:
                    self._binding_to_action[binding] = action
            else:
                self._action_to_bindings[action] = []

    def get_bindings_for_action(self, name):
        """ Returns a list of (keycode, modifier) for the action C{name}. """
        return self._action_to_bindings[name]

_manager = None


def keybinding_manager(window):
    """ Returns a singleton instance of the keybinding manager. """
    global _manager
    if _manager:
        return _manager
    else:
        _manager = _KeybindingManager(window)
        return _manager

# vim: expandtab:sw=4:ts=4
