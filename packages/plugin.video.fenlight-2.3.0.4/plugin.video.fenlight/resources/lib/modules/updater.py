# -*- coding: utf-8 -*-
import json
import requests
import shutil
from os import path
from zipfile import ZipFile
from caches.settings_cache import get_setting, set_setting
from modules.utils import string_alphanum_to_num, unzip
from modules import kodi_utils
from modules.sevenplus import BUNDLED_DEPENDENCIES
logger = kodi_utils.logger

def update_branch():
	branch = get_setting('fenlight.update.branch') or get_setting('update.branch') or 'main'
	branch = (branch or '').strip()
	return branch if branch else 'main'

def get_location(insert=''):
	username = get_setting('fenlight.update.username') or get_setting('update.username') or 'massimo233'
	location = get_setting('fenlight.update.location') or get_setting('update.location') or 'Slzstream.github.io'
	location = location.replace('/packages', '').strip('/')
	return 'https://raw.githubusercontent.com/%s/%s/%s/packages/%s' % (
		username,
		location,
		update_branch(),
		insert,
	)

def _zip_has_member(zip_file, member):
	names = zip_file.namelist()
	if member in names:
		return True
	alt = member.replace('/', '\\')
	if alt in names:
		return True
	normalized_member = member.replace('\\', '/').rstrip('/')
	for name in names:
		if name.replace('\\', '/').rstrip('/') == normalized_member:
			return True
	return False

def _validate_fenlight_zip(zip_location):
	try:
		with open(zip_location, 'rb') as handle:
			if handle.read(2) != b'PK':
				return False
		with ZipFile(zip_location) as zip_file:
			required = (
				'plugin.video.fenlight/addon.xml',
				'plugin.video.fenlight/resources/lib/fenlight.py',
			)
			return all(_zip_has_member(zip_file, item) for item in required)
	except Exception as e:
		logger('Fen Light Updater Error', 'Zip validation failed: %s' % str(e))
		return False

def _bundled_packages_path():
	return path.join(kodi_utils.translate_path('special://home/addons/plugin.video.fenlight/'), 'resources', 'packages')

def _dependency_ready(dep, addons_path):
	return kodi_utils.path_exists(path.join(addons_path, dep['folder'], 'addon.xml'))

def _stage_package_zip(dep, packages_path):
	zip_location = path.join(packages_path, dep['zip'])
	local_zip = path.join(_bundled_packages_path(), dep['zip'])
	if kodi_utils.path_exists(local_zip):
		try:
			shutil.copyfile(local_zip, zip_location)
			return zip_location
		except Exception as e:
			logger('Fen Light 7plus Dependency Error', 'Local copy failed for %s: %s' % (dep['zip'], str(e)))
	url = get_location(dep['zip'])
	if _download_package(url, zip_location):
		return zip_location
	return None

def _download_package(url, zip_location):
	try:
		result = requests.get(url, timeout=120)
	except Exception as e:
		logger('Fen Light Updater Error', 'Download failed: %s' % str(e))
		return False
	if result.status_code != 200:
		logger('Fen Light Updater Error', 'Download HTTP %s for %s' % (result.status_code, url))
		return False
	if not result.content or result.content[:2] != b'PK':
		logger('Fen Light Updater Error', 'Download is not a zip file: %s' % url)
		return False
	packages_path = path.dirname(zip_location)
	if not kodi_utils.path_exists(packages_path):
		kodi_utils.make_directory(packages_path)
	with open(zip_location, 'wb') as handle:
		handle.write(result.content)
	return True

def _format_dependency_status(status):
	if status.get('installed'):
		text = '[CR][CR]Installed 7plus components: [B]%s[/B]' % ', '.join(status['installed'])
	else:
		text = ''
	if status.get('failed'):
		text += '[CR][CR]7plus component install failed: [B]%s[/B]' % ', '.join(status['failed'])
	return text

def get_versions():
	try:
		result = requests.get(get_location('fenlightam_version'))
		if result.status_code != 200:
			kodi_utils.notification('Fen Light update check failed: %s' % result.status_code, 3000)
			return None, None
		online_version = result.text.strip()
		current_version = kodi_utils.addon_version()
		return current_version, online_version
	except Exception as e:
		logger('Fen Light Updater Error', str(e))
		kodi_utils.notification('Fen Light update check failed', 3000)
		return None, None

def get_changes(online_version=None):
	try:
		if not online_version:
			current_version, online_version = get_versions()
			if not version_check(current_version, online_version): return kodi_utils.ok_dialog(heading='Fen Light Updater',
				text='You are running the current version of Fen Light.[CR][CR]There is no new version changelog to view.')
		kodi_utils.show_busy_dialog()
		result = requests.get(get_location('fenlightam_changes'))
		kodi_utils.hide_busy_dialog()
		if result.status_code != 200: return kodi_utils.notification('Error', icon=kodi_utils.get_icon('downloads'))
		changes = result.text
		return kodi_utils.show_text('New Online Release (v.%s) Changelog' % online_version, text=changes, font_size='large')
	except:
		kodi_utils.hide_busy_dialog()
		return kodi_utils.notification('Error', icon=kodi_utils.get_icon('downloads'))

def version_check(current_version, online_version):
	return string_alphanum_to_num(current_version) != string_alphanum_to_num(online_version)

def update_check(action=4):
	if action == 3: return
	current_version, online_version = get_versions()
	if not current_version: return
	show_after_action = True
	if not version_check(current_version, online_version):
		if action == 4: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Installed Version: [B]%s[/B][CR]Online Version: [B]%s[/B][CR][CR] %s' \
			% (current_version, online_version, '[B]No Update Available[/B]'))
		return
	if action in (0, 4):
		if not kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Installed Version: [B]%s[/B][CR]Online Version: [B]%s[/B][CR][CR] %s' \
			% (current_version, online_version, '[B]An Update is Available[/B][CR]Perform Update?'), ok_label='Yes', cancel_label='No'): return
		if kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Do you want to view the changelog for the new release before installing?', ok_label='Yes', cancel_label='No'):
			get_changes(online_version)
			if not kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Continue with Update After Viewing Changes?', ok_label='Yes', cancel_label='No'): return
			show_after_action = False
	if action == 1: kodi_utils.notification('Fen Light Update Occuring', icon=kodi_utils.get_icon('downloads'))
	elif action == 2: return kodi_utils.notification('Fen Light Update Available', icon=kodi_utils.get_icon('downloads'))
	return update_addon(online_version, action, show_after_action)

def rollback_check():
	current_version = get_versions()[0]
	url = 'https://api.github.com/repos/%s/%s/contents/packages' % (
		get_setting('fenlight.update.username') or get_setting('update.username'),
		get_setting('fenlight.update.location') or get_setting('update.location'),
	)
	kodi_utils.show_busy_dialog()
	results = requests.get(url, params={'ref': update_branch()})
	kodi_utils.hide_busy_dialog()
	if results.status_code != 200: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error rolling back.[CR]Please install rollback manually')
	results = results.json()
	results = [i['name'].split('-')[1].replace('.zip', '') for i in results if 'plugin.video.fenlight' in i['name'] \
				and not i['name'].split('-')[1].replace('.zip', '') == current_version]
	if not results: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='No previous versions found.[CR]Please install rollback manually')
	results.sort(reverse=True)
	list_items = [{'line1': item, 'icon': kodi_utils.get_icon('downloads')} for item in results]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Rollback Version'}
	rollback_version = kodi_utils.select_dialog(results, **kwargs)
	if rollback_version == None: return
	if not kodi_utils.confirm_dialog(heading='Fen Light Updater',
		text='Are you sure?[CR]Version [B]%s[/B] will overwrite your current installed version.[CR]Fen Light will set your update action to [B]OFF[/B] if rollback is successful' \
		% rollback_version): return
	update_addon(rollback_version, 5)

def update_addon(new_version, action, show_after_action=True):
	kodi_utils.close_all_dialog()
	kodi_utils.execute_builtin('ActivateWindow(Home)', True)
	kodi_utils.notification('Fen Light Performing Rollback' if action == 5 else 'Fen Light Performing Update', icon=kodi_utils.get_icon('downloads'))
	zip_name = 'plugin.video.fenlight-%s.zip' % new_version
	url = get_location('%s') % zip_name
	kodi_utils.show_busy_dialog()
	if not _download_package(url, path.join(kodi_utils.translate_path('special://home/addons/packages/'), zip_name)):
		kodi_utils.hide_busy_dialog()
		return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error Updating.[CR]Please install new update manually.[CR][CR]Could not download update package.')
	kodi_utils.hide_busy_dialog()
	zip_location = path.join(kodi_utils.translate_path('special://home/addons/packages/'), zip_name)
	if not _validate_fenlight_zip(zip_location):
		kodi_utils.delete_file(zip_location)
		return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error Updating.[CR]Downloaded package is invalid.[CR][CR]Please install new update manually.')
	shutil.rmtree(path.join(kodi_utils.translate_path('special://home/addons/'), 'plugin.video.fenlight'))
	success = unzip(zip_location, kodi_utils.translate_path('special://home/addons/'), kodi_utils.translate_path('special://home/addons/plugin.video.fenlight/'))
	kodi_utils.delete_file(zip_location)
	if not success: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error Updating.[CR]Please install new update manually')
	kodi_utils.update_local_addons()
	kodi_utils.disable_enable_addon()
	kodi_utils.update_kodi_addons_db()
	from caches.navigator_cache import navigator_cache
	navigator_cache.sync_default_menus(notify=True)
	kodi_utils.show_busy_dialog()
	dep_status = install_bundled_dependencies(silent=True)
	kodi_utils.hide_busy_dialog()
	dep_text = _format_dependency_status(dep_status)
	if action == 5:
		set_setting('update.action', '3')
		kodi_utils.ok_dialog(heading='Fen Light Updater', text='[CR]Success.[CR]Fen Light rolled back to version [B]%s[/B]' % new_version)
	elif action in (0, 4):
		success_text = '[CR]Success.[CR]Fen Light updated to version [B]%s[/B]%s' % (new_version, dep_text)
		if show_after_action:
			if kodi_utils.confirm_dialog(heading='Fen Light Updater', text=success_text, ok_label='Changelog', cancel_label='Exit', default_control=10) != False:
				kodi_utils.show_text('Changelog', file=kodi_utils.translate_path('special://home/addons/plugin.video.fenlight/resources/text/changelog.txt'), font_size='large')
		else:
			kodi_utils.ok_dialog(heading='Fen Light Updater', text=success_text)
	kodi_utils.refresh_widgets()

def install_bundled_dependencies(silent=False):
	addons_path = kodi_utils.translate_path('special://home/addons/')
	packages_path = kodi_utils.translate_path('special://home/addons/packages/')
	if not kodi_utils.path_exists(packages_path):
		kodi_utils.make_directory(packages_path)
	installed = []
	failed = []
	for dep in BUNDLED_DEPENDENCIES:
		if _dependency_ready(dep, addons_path):
			continue
		if not silent:
			kodi_utils.notification('Installing %s...' % dep['id'], 2500)
		zip_location = _stage_package_zip(dep, packages_path)
		if not zip_location:
			logger('Fen Light 7plus Dependency Error', 'Could not stage %s' % dep['zip'])
			failed.append(dep['id'])
			continue
		try:
			with ZipFile(zip_location) as zip_file:
				if not _zip_has_member(zip_file, dep['check']):
					logger('Fen Light 7plus Dependency Error', 'Invalid package contents for %s' % dep['zip'])
					kodi_utils.delete_file(zip_location)
					failed.append(dep['id'])
					continue
		except Exception as e:
			logger('Fen Light 7plus Dependency Error', '%s: %s' % (dep['zip'], str(e)))
			kodi_utils.delete_file(zip_location)
			failed.append(dep['id'])
			continue
		dest_folder = path.join(addons_path, dep['folder'])
		if kodi_utils.path_exists(dest_folder):
			shutil.rmtree(dest_folder)
		success = unzip(zip_location, addons_path, path.join(addons_path, dep['folder'], 'addon.xml'), show_busy=not silent)
		kodi_utils.delete_file(zip_location)
		if not success:
			logger('Fen Light 7plus Dependency Error', 'Extract failed for %s' % dep['id'])
			failed.append(dep['id'])
			continue
		installed.append(dep['id'])
	if installed:
		kodi_utils.update_local_addons()
		kodi_utils.update_kodi_addons_db()
	return {'success': not failed, 'installed': installed, 'failed': failed}
