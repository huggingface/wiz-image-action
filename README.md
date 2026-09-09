# Wiz Image Action

Two GitHub Actions that put the [Wiz CLI](https://docs.wiz.io/docs/wiz-cli-overview) into a container image build. One scans the image before you push it. The other binds the scan to the digest in the registry, which adds the image to the Wiz trusted image database.

Wiz publishes no GitHub Action of its own. These actions wrap the documented commands, and they add the two things a pipeline needs: a clear result when a policy blocks an image, and a digest that the Wiz admission controller can find.

| Action | When to run it |
|---|---|
| `huggingface/wiz-image-action/scan@v1` | After the build, **before** the push |
| `huggingface/wiz-image-action/register@v1` | After the push, in the **same job** |

## Usage

```yaml
      - name: Build the image
        id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          load: true            # the Wiz CLI reads the local image store
          tags: ${{ env.IMAGE }}

      - name: Scan the image with Wiz
        id: scan
        uses: huggingface/wiz-image-action/scan@v1
        with:
          image: ${{ env.IMAGE }}
          clientId: ${{ vars.WIZ_CLIENT_ID }}
          clientSecret: ${{ secrets.WIZ_CLIENT_SECRET }}
          dockerfile: Dockerfile

      - name: Push the image
        id: push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ env.IMAGE }}

      - name: Register the image with Wiz
        uses: huggingface/wiz-image-action/register@v1
        with:
          image: ${{ steps.scan.outputs.image }}
          digest: ${{ steps.push.outputs.digest }}
          clientId: ${{ vars.WIZ_CLIENT_ID }}
          clientSecret: ${{ secrets.WIZ_CLIENT_SECRET }}
```

## Two constraints you must respect

**The Wiz CLI never pulls an image.** It reads the local image store. If the image is not there, the scan stops with `unknown image [<ref>]`. Build with `load: true`, or pull the image before you scan it. This is also why the build and the push are two steps: Wiz recommends that you scan after the build but before the push, to keep unscanned images out of your registry.

**The register action must run in the same job as the scan.** The Wiz CLI keeps the scan in state on the runner, and it finds that scan by the image reference. A separate job gets a different runner, and the scan is not there. For the same reason, these are composite actions and not a reusable workflow.

## Inputs

### `scan`

| Input | Required | Default | Description |
|---|---|---|---|
| `image` | yes | | Image reference, with its tag or digest. It must exist locally. A path to a `.tar`, `.tar.gz` or `.tgz` file also works. |
| `clientId` | yes | | Client ID of the Wiz service account. |
| `clientSecret` | yes | | Client secret of the Wiz service account. |
| `policies` | no | *(tenant default)* | Wiz policy names to apply, separated by commas. |
| `dockerfile` | no | | Path to the Dockerfile. Wiz keeps it as metadata and uses it to correlate the image with its source code. |
| `enforcement` | no | `policy` | `policy` uses the exit code of the Wiz CLI, so your Wiz policy decides. `audit` prints a warning and continues. |
| `reportPath` | no | *(runner temp)* | File to write the JSON scan report to. |
| `projects` | no | *(service account)* | Wiz project IDs or slugs, separated by commas. |

Outputs: `image` is the reference that was scanned, so pass it to `register`. `verdict` is `passed` or `failed`. `report` is the path to the JSON report.

### `register`

| Input | Required | Default | Description |
|---|---|---|---|
| `image` | yes | | The same reference that you gave to `scan`. |
| `digest` | no | | Digest of the image in the registry. Give this value when the local image has no digest of its own. |
| `clientId` | yes | | Client ID of the Wiz service account. |
| `clientSecret` | yes | | Client secret of the Wiz service account. |
| `projects` | no | *(service account)* | Wiz project IDs or slugs, separated by commas. |

## When to give `digest`

Give it whenever the image in the local store has no digest of its own. An image that `buildx` pushed is the common case, because `buildx` pushes from its own cache and leaves no digest on the local image. An image exported to a `.tar` file is the other case. Take the value from the `digest` output of `docker/build-push-action`.

You can leave `digest` empty only when `docker push` sent the local image to the registry, because that push writes the digest back onto the local image.

The action checks this for you. If the local image carries no digest and you gave none, the step fails with that advice, rather than registering nothing and letting the problem appear later as an admission verdict on a cluster.

## Enforcement

The Wiz CLI stops with exit code 4 when the image hits a policy whose CLI enforcement is `BLOCK`. That enforcement is a setting on the policy in Wiz, not in this action. So:

- `enforcement: policy` — the default. The step fails if, and only if, Wiz says the policy blocks the image. Change the decision in Wiz, not in every workflow that calls this action.
- `enforcement: audit` — the step prints a warning and continues. Use this while you onboard a repository whose image does not pass yet.

Any other non-zero exit code is a failure of the CLI itself. The step always fails then, whatever `enforcement` says.

`audit` is visible only in the workflow file that sets it. Wiz does not know about it, and Wiz does not remove an image from its trusted image database. So a repository left on `audit` is not "not enforced yet" — it is exempt, and its images are still admitted. Keep a list of the repositories that set it, and clear that list before you rely on the gate.

## Multi-architecture images

A manifest list has a digest of its own, and it is different from the digest of each architecture. Kubernetes resolves the manifest list. So a build that produces one manifest list from several per-architecture images must decide which digest to register. Wiz does not document this case. Test it against a real admission verdict before you rely on it.

There is a second limit in the same area. `load: true` puts one architecture into the local image store, so the scan covers that architecture only. The other architectures of the same manifest list are never scanned.

## Service account

Create a Wiz CLI deployment, which gives you a service account of type `CLI` and its two values. In the Wiz portal, use **Connect to Wiz**, then **CI/CD Platforms**, then **GitHub**. Do not use the general **New Service Account** form, because it does not offer the `CLI` type.

Store the client ID as a variable and the client secret as a secret. Organization level works, and it saves you from repeating the setup in every repository.

## Wiz CLI version

Both actions download the current Wiz CLI. There is no input to choose a version, because Wiz serves no versioned download path — every `/v1/wizcli/<version>/` URL answers 403, so `latest` is the only reference that exists.

Wiz does publish a version-pinned container image, `public-registry.wiz.io/wiz-app/wizcli:1`. These actions do not use it, because a container cannot read the local image store of the runner without the Docker socket.

## Releasing

A merge to `main` releases. `semantic-release` reads the conventional-commit messages, works out the next version, and creates the tag and the GitHub release. The same job then moves the `v1` tag onto the new commit.

Merges are squashed, so **the pull request title is the message that decides the version**:

| Title starts with | Result |
|---|---|
| `fix:` | patch, and `v1` follows |
| `feat:` | minor, and `v1` follows |
| `feat!:`, or a `BREAKING CHANGE:` footer | major. This creates `v2` and leaves `v1` where it is. |
| `chore:`, `ci:`, `docs:`, `refactor:` | no release |

A patch or a minor release reaches every caller pinned to `@v1` on their next workflow run. Mark a breaking change as breaking, or you ship it to all of them.

A pre-release version never moves the major tag.

## License

Apache-2.0.
