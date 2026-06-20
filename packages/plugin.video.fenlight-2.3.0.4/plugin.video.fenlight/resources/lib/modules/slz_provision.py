# -*- coding: utf-8 -*-
"""Slzstream TorBox provisioning: 6-digit claim code + operator fulfill + poll."""
from datetime import datetime, timezone

import requests
import xbmc
import xbmcgui

from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils

_SSL_WARNINGS_DISABLED = False


def _provision_request_kwargs(timeout=20):
	"""HTTPS verify follows provision.allow_self_signed (for VPS self-signed certs)."""
	global _SSL_WARNINGS_DISABLED
	allow = get_setting('fenlight.provision.allow_self_signed', 'false')
	verify = allow not in ('true', '1')
	kwargs = {'timeout': timeout, 'verify': verify}
	if not verify and not _SSL_WARNINGS_DISABLED:
		try:
			import urllib3
			urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
			_SSL_WARNINGS_DISABLED = True
		except Exception:
			pass
	return kwargs


def _apply_torbox_key(api_key):
	from apis.torbox_api import TorBoxAPI

	tb = TorBoxAPI()
	tb.token = api_key
	try:
		info = tb.account_info()
		customer = info['data']['customer']
	except Exception:
		return kodi_utils.ok_dialog(heading='Slzstream', text='The key failed TorBox validation.')
	set_setting('tb.token', api_key)
	set_setting('tb.enabled', 'true')
	try:
		from apis.torbox_api import TorBox

		TorBox.clear_cache()
	except Exception:
		pass
	kodi_utils.notification('TorBox authorized via Slzstream', 3000)
	return kodi_utils.ok_dialog(
		heading='Slzstream',
		text='Success. TorBox is enabled on this device.[CR][CR]Account: [B]%s[/B]' % customer,
	)


def request_provisioning_claim():
	base = (get_setting('fenlight.provision.base_url') or '').strip().rstrip('/')
	if not base or base in ('empty_setting', ''):
		return kodi_utils.ok_dialog(heading='Slzstream', text='Set the provisioning server URL in settings first.')
	start_url = '%s/v1/provision/claim' % base
	poll_url = '%s/v1/provision/claim/poll' % base
	req_kw = _provision_request_kwargs()
	try:
		r = requests.post(start_url, **req_kw)
	except Exception as e:
		err = str(e)
		if base.lower().startswith('https') and req_kw.get('verify', True):
			err += '[CR][CR]If the server uses a self-signed certificate, enable [B]Allow self-signed SSL[/B] under Slzstream provisioning.'
		return kodi_utils.ok_dialog(heading='Slzstream', text='Could not reach server.[CR][CR]%s' % err)
	if r.status_code != 200:
		return kodi_utils.ok_dialog(heading='Slzstream', text='Start failed (HTTP %s).' % r.status_code)
	try:
		data = r.json()
	except Exception:
		return kodi_utils.ok_dialog(heading='Slzstream', text='Invalid response from server.')
	code = data.get('code')
	poll_token = data.get('poll_token')
	expires_at = data.get('expires_at')
	if not code or not poll_token:
		return kodi_utils.ok_dialog(heading='Slzstream', text='Server did not return a code.')
	try:
		exp = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
		total_seconds = max(30, int((exp - datetime.now(timezone.utc)).total_seconds()))
	except Exception:
		total_seconds = 300
	dialog = xbmcgui.DialogProgress()
	dialog.create('Slzstream provisioning', 'Code: [B]%s[/B][CR]Send this code to your provider.' % code)
	step = 2
	elapsed = 0
	while elapsed < total_seconds:
		if dialog.iscanceled():
			dialog.close()
			return kodi_utils.ok_dialog(
				heading='Slzstream',
				text='Cancelled. If the provider already submitted your key, start Request provisioning again.',
			)
		pct = min(100, int(elapsed * 100 / total_seconds))
		remaining = max(0, total_seconds - elapsed)
		line = 'Code [B]%s[/B] — send to provider. [CR]%d sec left' % (code, remaining)
		try:
			dialog.update(pct, line)
		except TypeError:
			dialog.update(pct)
		try:
			pr = requests.post(
				poll_url,
				json={'code': code, 'poll_token': poll_token},
				**req_kw,
			)
		except Exception:
			xbmc.sleep(step * 1000)
			elapsed += step
			continue
		if pr.status_code == 200:
			try:
				pd = pr.json()
			except Exception:
				pd = {}
			st = pd.get('status')
			if st == 'ready' and pd.get('torbox_api_key'):
				dialog.close()
				return _apply_torbox_key(pd['torbox_api_key'])
			if st == 'expired':
				dialog.close()
				return kodi_utils.ok_dialog(heading='Slzstream', text='This code expired. Request provisioning again.')
			if st == 'unknown':
				dialog.close()
				return kodi_utils.ok_dialog(heading='Slzstream', text='Session invalid. Request provisioning again.')
		xbmc.sleep(step * 1000)
		elapsed += step
	dialog.close()
	return kodi_utils.ok_dialog(heading='Slzstream', text='Timed out waiting. Request provisioning again if needed.')
