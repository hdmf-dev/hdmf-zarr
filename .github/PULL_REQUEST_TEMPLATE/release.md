Prepare for release of HDMF-Zarr [version]

### Before merging:
- [ ] Make sure all PRs to be included in this release have been merged to `dev`.
- [ ] Major and minor releases: Update dependency ranges in `pyproject.toml` as needed. The minimum versions are
  tested by the `py312-minimum` and `gallery-py312-minimum` tox environments.
- [ ] Update the GitHub Actions used in the workflows to their latest versions.
- [ ] Check legal file dates and information in `LICENSE.txt`, `README.rst`, `docs/source/conf.py`,
  and any other locations as needed
- [ ] Update `pyproject.toml` as needed
- [ ] Update `README.rst` as needed
- [ ] Update changelog (set release date) in `CHANGELOG.md` and any other docs as needed. The deploy workflow
  uses the section whose heading starts with `## [version] (` as the GitHub release notes.
- [ ] Run tests locally including gallery tests, and inspect all warnings and outputs
  (`pytest && python test_gallery.py`). Try to remove all warnings.
- [ ] Test docs locally and inspect all warnings and outputs `cd docs; make clean && make html`
- [ ] After pushing this branch to GitHub, manually trigger the "Run all tests" GitHub Actions workflow on this
  branch by going to https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_all_tests.yml, selecting
  "Run workflow" on the right, selecting this branch, and clicking "Run workflow". Make sure all tests pass.
- [ ] Check that the readthedocs build for this PR succeeds (see the PR check)

### After merging:
1. Create release by following steps in https://hdmf.readthedocs.io/en/stable/make_a_release.html or use alias `git pypi-release [tag]` if set up
2. After the "Deploy release" workflow creates the new release (wait ~10 min), verify that the release notes on the
   [GitHub releases page](https://github.com/hdmf-dev/hdmf-zarr/releases) include the changelog for this version
3. Check that the readthedocs "stable" build runs and succeeds
4. Either monitor [conda-forge/hdmf_zarr-feedstock](https://github.com/conda-forge/hdmf_zarr-feedstock) for the
   regro-cf-autotick-bot bot to create a PR updating the version of HDMF-Zarr to the latest PyPI release, usually within
   24 hours of release, or manually create a PR updating `recipe/meta.yaml` with the latest version number
   and SHA256 retrieved from PyPI > HDMF-Zarr > Download Files > View hashes for the `.tar.gz` file. Re-render and
   update the dependencies as needed.
