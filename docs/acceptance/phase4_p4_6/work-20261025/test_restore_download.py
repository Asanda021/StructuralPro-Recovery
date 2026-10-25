"""Restore only the authenticated Drive-redownloaded bytes, under offline QA."""
import runpy,sys

def test_downloaded_archive_independent_restore():
    sys.argv=['restore_backup.py','/workspace/scratch/5ff2acae0199/phase4-work-20261025-v2-redownload.zip','/tmp/sp-restored-work-20261025','6237e53d3906ceb26b50795271ccd555cf66896ce09a389654bb66602485b74b']
    runpy.run_path('docs/acceptance/phase4_p4_6/work-20261025/restore_backup.py',run_name='__main__')
