# wind-repo

An F-Droid Repo focused on offline capable and/or optimized apps.

To add an all, there just needs to be a _.yml_ file in _metadata/_
named after the Application ID of the app to be included.  The
`./scripts/update-apks.py` script will download from the repos listed
there as the sources of APKs.  The script will also fetch the
descriptive texts, translations, and graphics from there.  The only
thing that needs to be in the _.yml_ file is the `AutoName:` field
which gives the human name for the app, e.g. "Haven" in
_metadata/org.havenapp.main.yml_.

To override the description, name, or summary, add those fields to the
metadata _.yml_ file, and that will take precedence over what comes
from the original source repos.


## Adding map files

To add more map files:

* Edit the listing in `scripts/download-osmand-map-files.py`.
* Add 512x512 PNG icon to `graphics/` using the same file name, but with `.png` appended.

