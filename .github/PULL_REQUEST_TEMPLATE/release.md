Prepare for release of HDMF-Zarr [version]

### Before merging:
- [ ] Make sure all PRs to be included in this release have been merged to `dev`.
- [ ] Major and minor releases: Update dependency ranges in `pyproject.toml` and minimums in 
  `requirements-min.txt` as needed.
- [ ] Check legal file dates and information in `Legal.txt`, `license.txt`, `README.rst`, `docs/source/conf.py`,
  and any other locations as needed
- [ ] Update `pyproject.toml` as needed
- [ ] Update `README.rst` as needed
- [ ] Update changelog (set release date) in `CHANGELOG.md` and any other docs as needed
- [ ] Run tests locally including gallery tests, and inspect all warnings and outputs
  (`pytest && python test_gallery.py`)
- [ ] Test docs locally and inspect all warnings and outputs `cd docs; make clean && make html`
- [ ] After pushing this branch to GitHub, manually trigger the "Run all tests" GitHub Actions workflow on this
  branch by going to https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_all_tests.yml, selecting
  "Run workflow" on the right, selecting this branch, and clicking "Run workflow". Make sure all tests pass.
- [ ] Check that the readthedocs build for this PR succeeds (see the PR check)

### After merging:
1. Create release by following steps in `docs/source/make_a_release.rst` or use alias `git pypi-release [tag]` if set up
2. After the CI bot creates the new release (wait ~10 min), update the release notes on the
   [GitHub releases page](https://github.com/hdmf-dev/hdmf-zarr/releases) with the changelog
3. Check that the readthedocs "latest" build runs and succeeds
4. Either monitor [conda-forge/hdmf_zarr-feedstock](https://github.com/conda-forge/hdmf_zarr-feedstock) for the
   regro-cf-autotick-bot bot to create a PR updating the version of HDMF to the latest PyPI release, usually within
   24 hours of release, or manually create a PR updating `recipe/meta.yaml` with the latest version number
   and SHA256 retrieved from PyPI > HDMF-Zarr > Download Files > View hashes for the `.tar.gz` file. Re-render and 
   update the dependencies as needed.
