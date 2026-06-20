# -*- coding: utf-8 -*-
"""7plus integration: proxy slyguy.7plus routes through FenLightAM."""
import os
import sys
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


def addons_installed():
	return k.addon_installed(ADDON_DEPS) and k.addon_installed(ADDON_SLYGUY) and k.addon_installed(ADDON_7PLUS)


def get_icon():
	try:
		return xbmcaddon.Addon(ADDON_7PLUS).getAddonInfo('icon')
	except:
		return k.get_icon('7plus')


def proxy_url(route='', **kwargs):
	params = {'mode': 'sevenplus.dispatch'}
	if route:
		params['_'] = route
	for key, value in kwargs.items():
		if value is None or key in ('mode', '_addon_id'):
			continue
		params[key] = value
	return k.build_url(params)


def build_slyguy_url(params):
	data = dict(params)
	data.pop('mode', None)
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
	os.environ['ADDON_ID'] = ADDON_7PLUS
	addon_path = xbmcaddon.Addon(ADDON_7PLUS).getAddonInfo('path')
	if addon_path not in sys.path:
		sys.path.insert(0, addon_path)
	from resources.lib import plugin as plugin_module
	_plugin_module = plugin_module
	return plugin_module


def dispatch(params):
	if not addons_installed():
		return install_dependencies()
	url = build_slyguy_url(params)
	_patch_build_url()
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


def install_dependencies():
	from modules import updater
	if not k.confirm_dialog(heading='7plus', text='7plus requires additional components from Slzstream.[CR][CR]Install them now?'):
		return
	result = updater.install_bundled_dependencies()
	if result and addons_installed():
		k.notification('7plus components installed', 3000)
		return dispatch({'mode': 'sevenplus.dispatch'})
	return k.ok_dialog(heading='7plus', text='Could not install all 7plus components.[CR][CR]Try updating FenLightAM from Tools, or install the zips from the Slzstream repo manually.')


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
