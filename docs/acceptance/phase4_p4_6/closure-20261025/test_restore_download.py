"""Independent restore using only authenticated Drive-redownloaded bytes."""
import runpy,sys

def test_downloaded_closure_archive_restores():
 sys.argv=['restore_backup.py','/workspace/scratch/5ff2acae0199/phase4-closure-redownload-20261025.zip','/tmp/sp-restored-closure-final-20261025','30bffdbc590b7847f5f9a01cb50dca3ee37a9795d5480adc3ff343a084fe7e8b']
 runpy.run_path('docs/acceptance/phase4_p4_6/closure-20261025/restore_backup.py',run_name='__main__')
