# -*- coding: utf-8 -*-
"""7plus integration: proxy slyguy.7plus routes through FenLightAM."""
import os
import sys
import traceback
from urllib.parse import urlencode

import xbmcaddon

from modules import kodi_utils as k

ADDON_7PLUS = 'slyguy.7plus'
ADDON_SLYGUY = 'script.module.slyguy'
ADDON_DEPS = 'slyguy.dependencies'
BUNDLED_DEPENDENCIES = [
	{'id': ADDON_DEPS, 'zip': 'slyguy.dependencies-0.0.30.zip', 'folder': ADDON_DEPS, 'check': '%s/addon.xml' % ADDON_DEPS},
	{'id': ADDON_SLYGUY, 'zip': 'script.module.slyguy-0.86.88.zip', 'folder': ADDON_SLYGUY, 'check': '%s/addon.xml' % ADDON_SLYGUY},
	{'id': ADDON_7PLUS, 'zip': 'slyguy.7plus-0.5.5.zip', 'folder': ADDON_7PLUS, 'check': '%s/addon.xml' % ADDON_7PLUS},
]

_plugin_module = None
_original_build_url = None
_runtime_ready = None


def _addons_path():
	return k.translate_path('special://home/addons/')


def _addon_root(addon_id):
	try:
		addon_path = xbmcaddon.Addon(addon_id).getAddonInfo('path')
		if addon_path:
			addon_path = k.translate_path(addon_path)
			if k.path_exists(os.path.join(addon_path, 'addon.xml')):
				return addon_path
	except Exception:
		pass
	fallback = os.path.join(_addons_path(), addon_id)
	if k.path_exists(os.path.join(fallback, 'addon.xml')):
		return fallback
	return None


def _addon_modules_path(addon_id):
	root = _addon_root(addon_id)
	if not root:
		return None
	modules_path = os.path.join(root, 'resources', 'modules')
	return modules_path if k.path_exists(modules_path) else None


def _clear_slyguy_modules():
	for name in list(sys.modules):
		if name == 'slyguy' or name.startswith('slyguy.'):
			del sys.modules[name]


def bootstrap_runtime():
	paths = []
	for addon_id in (ADDON_DEPS, ADDON_SLYGUY):
		modules_path = _addon_modules_path(addon_id)
		if modules_path:
			paths.append(modules_path)
	sevenplus_root = _addon_root(ADDON_7PLUS)
	if sevenplus_root:
		paths.append(sevenplus_root)
	for modules_path in reversed(paths):
		if modules_path not in sys.path:
			sys.path.insert(0, modules_path)
	os.environ['ADDON_ID'] = ADDON_7PLUS
	return paths


def runtime_ready(force=False):
	global _runtime_ready
	if force:
		_runtime_ready = None
		_clear_slyguy_modules()
	if _runtime_ready is not None:
		return _runtime_ready
	paths = bootstrap_runtime()
	if not paths:
		k.logger('7plus Bootstrap Error', 'SlyGuy module paths were not found on disk')
		_runtime_ready = False
		return _runtime_ready
	try:
		import xbmcaddon as xbmcaddon_module
		_original_addon = xbmcaddon_module.Addon

		def _default_addon(addon_id=None):
			return _original_addon(addon_id or ADDON_7PLUS)

		xbmcaddon_module.Addon = _default_addon
		try:
			import slyguy  # noqa: F401
			_runtime_ready = True
		finally:
			xbmcaddon_module.Addon = _original_addon
	except Exception as e:
		k.logger('7plus Bootstrap Error', '%s\n%s' % (str(e), traceback.format_exc()))
		_runtime_ready = False
	return _runtime_ready


def _dependency_ready(dep):
	return _addon_root(dep['folder']) is not None


def addons_installed():
	if not all(_dependency_ready(dep) for dep in BUNDLED_DEPENDENCIES):
		return False
	return runtime_ready()


def get_icon():
	local_icon = os.path.join(k.addon_info('path'), 'resources', 'media', 'icons', '7plus.png')
	if k.path_exists(local_icon):
		return k.translate_path(local_icon)
	try:
		return xbmcaddon.Addon(ADDON_7PLUS).getAddonInfo('icon')
	except:
		return k.get_icon('7plus')


def proxy_url(route='', **kwargs):
	params = {'mode': 'sevenplus.dispatch'}
	if route:
		params['_'] = route
	for key, value in kwargs.items():
		if value is None or key in ('mode', '_addon_id', 'iconImage', 'name'):
			continue
		params[key] = value
	return k.build_url(params)


def build_slyguy_url(params):
	data = dict(params)
	data.pop('mode', None)
	for key in ('iconImage', 'name', 'isFolder'):
		data.pop(key, None)
	route = data.pop('_', '') or ''
	query = {}
	if route:
		query['_'] = route
	for key, value in data.items():
		if value is not None:
			query[key] = value
	return 'plugin://%s/?%s' % (ADDON_7PLUS, urlencode(query))


def _patch_build_url():
	import slyguy.router as router
	global _original_build_url
	if _original_build_url is None:
		_original_build_url = router.build_url

	def _fenlight_build_url(_url, _addon_id=None, **kwargs):
		return proxy_url(_url or '', **kwargs)

	router.build_url = _fenlight_build_url


def _unpatch_build_url():
	import slyguy.router as router
	global _original_build_url
	if _original_build_url:
		router.build_url = _original_build_url


def _load_plugin():
	global _plugin_module
	if _plugin_module:
		return _plugin_module
	addon_path = _addon_root(ADDON_7PLUS)
	if not addon_path:
		raise RuntimeError('7plus addon path not found')
	if addon_path not in sys.path:
		sys.path.insert(0, addon_path)
	from resources.lib import plugin as plugin_module
	_plugin_module = plugin_module
	return plugin_module


def dispatch(params):
	if not all(_dependency_ready(dep) for dep in BUNDLED_DEPENDENCIES):
		return install_dependencies()
	if not runtime_ready():
		return install_dependencies(retry=True)
	_patch_build_url()
	url = build_slyguy_url(params)
	try:
		_load_plugin().plugin.dispatch(url)
	except Exception as e:
		k.logger('7plus Dispatch Error', str(e))
		return k.ok_dialog(heading='7plus', text='Could not open 7plus.[CR][CR]%s' % str(e))
	finally:
		_unpatch_build_url()


def open_settings():
	if not addons_installed():
		return install_dependencies()
	return k.execute_builtin('Addon.OpenSettings(%s)' % ADDON_7PLUS)


def install_dependencies(retry=False):
	from modules import updater
	heading = '7plus'
	if retry:
		text = '7plus components are installed but could not be loaded.[CR][CR]Reinstall them now?'
	else:
		text = '7plus requires additional components.[CR][CR]Install them now?'
	if not retry and not k.confirm_dialog(heading=heading, text=text):
		return
	status = updater.install_bundled_dependencies(silent=False, force=retry)
	if status.get('success') and runtime_ready(force=True):
		k.notification('7plus components ready', 3500)
		return dispatch({'mode': 'sevenplus.dispatch'})
	text = 'Could not install all 7plus components.'
	if status.get('installed'):
		text += '[CR][CR]Installed: %s' % ', '.join(status['installed'])
	if status.get('failed'):
		text += '[CR][CR]Failed: %s' % ', '.join(status['failed'])
	if status.get('pending_restart'):
		text += '[CR][CR]Components are installed. Restart Kodi, then open 7plus again.'
	elif not runtime_ready(force=True):
		text += '[CR][CR]The SlyGuy Python module could not be loaded. Restart Kodi and try again.'
	return k.ok_dialog(heading=heading, text=text)


def menu_items():
	return [
		{'label': 'Browse 7plus', 'route': '', 'icon': '7plus'},
		{'label': 'Live TV', 'route': 'live_tv', 'icon': '7plus'},
		{'label': 'Shows', 'route': 'shows', 'icon': '7plus'},
		{'label': 'Featured', 'route': 'content', 'slug': 'ctv-home', 'icon': '7plus'},
		{'label': 'Categories', 'route': 'content', 'slug': 'all-categories', 'icon': '7plus'},
		{'label': 'Search', 'route': 'search', 'icon': '7plus'},
		{'label': 'Bookmarks', 'route': '_bookmarks', 'icon': '7plus'},
		{'label': 'Login', 'route': 'login', 'icon': '7plus', 'isFolder': 'false'},
		{'label': 'Settings', 'route': '_settings', 'icon': 'settings', 'isFolder': 'false'},
	]
