#!/usr/bin/env python3
"""Build legacy-compatible Kodi addon zips for Slzstream packages."""
import os
import shutil
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'packages'))
FENLIGHT_SRC = os.path.join(ROOT, 'plugin.video.fenlight-2.3.0.4', 'plugin.video.fenlight')
FENLIGHT_PACKAGES = os.path.join(FENLIGHT_SRC, 'resources', 'packages')

BUNDLED_IN_FENLIGHT = [
	'slyguy.dependencies-0.0.30.zip',
	'script.module.slyguy-0.86.88.zip',
	'slyguy.7plus-0.5.5.zip',
]

RELEASES = [
	(FENLIGHT_SRC, 'plugin.video.fenlight', 'plugin.video.fenlight-3.0.9.zip'),
	('slyguy.dependencies', 'slyguy.dependencies', 'slyguy.dependencies-0.0.30.zip'),
	('script.module.slyguy', 'script.module.slyguy', 'script.module.slyguy-0.86.88.zip'),
	('slyguy.7plus', 'slyguy.7plus', 'slyguy.7plus-0.5.5.zip'),
]


def sync_bundled_packages():
	os.makedirs(FENLIGHT_PACKAGES, exist_ok=True)
	for zip_name in BUNDLED_IN_FENLIGHT:
		source = os.path.join(ROOT, zip_name)
		target = os.path.join(FENLIGHT_PACKAGES, zip_name)
		if not os.path.isfile(source):
			raise SystemExit('Missing dependency zip: %s' % source)
		shutil.copy2(source, target)


def build_addon_zip(source_dir, zip_path, root_folder):
	source_dir = os.path.abspath(source_dir)
	with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
		for root, _, files in os.walk(source_dir):
			for name in files:
				full = os.path.join(root, name)
				rel = os.path.relpath(full, source_dir).replace('\\', '/')
				zf.write(full, '%s/%s' % (root_folder, rel))


def main():
	for source, folder, zip_name in RELEASES[1:]:
		source_path = os.path.join(ROOT, source)
		zip_path = os.path.join(ROOT, zip_name)
		if not os.path.isdir(source_path):
			raise SystemExit('Missing source directory: %s' % source_path)
		build_addon_zip(source_path, zip_path, folder)
		print('Built %s' % zip_name)
	sync_bundled_packages()
	build_addon_zip(FENLIGHT_SRC, os.path.join(ROOT, RELEASES[0][2]), RELEASES[0][1])
	print('Built %s' % RELEASES[0][2])


if __name__ == '__main__':
	main()
