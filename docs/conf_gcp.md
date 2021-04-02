# Configuration for Google Cloud Platform backend (`gcp`)

1. Sign up for a Google account.
2. Go to [Google Project](https://console.developers.google.com/project) page and click "SIGN UP FOR FREE TRIAL" on the top left and agree to terms.
3. Set up a payment method and click "START MY FREE TRIAL".
4. Create a [Google Project](https://console.developers.google.com/project) `[YOUR_PROJECT_NAME]` and choose it on the top of the page.
5. Create a [Google Cloud Storage bucket](https://console.cloud.google.com/storage/browser) `gs://[YOUR_BUCKET_NAME]` by clicking on a button "CREATE BUCKET" and create it to store pipeline outputs.
6. Find and enable following APIs in your [API Manager](https://console.developers.google.com/apis/library). Click a back button on your web brower after enabling each.
    * Compute Engine API
    * Google Cloud Storage (DO NOT click on "Create credentials")
    * Google Cloud Storage JSON API
    * Genomics API
    * **Google Cloud Life Sciences API** (for Cromwell's new API, i.e. `--use-google-cloud-life-sciences`)

7. Install [Google Cloud Platform SDK](https://cloud.google.com/sdk/downloads) and authenticate through it. You will be asked to enter verification keys. Get keys from the URLs they provide.
    ```bash
    $ gcloud auth login --no-launch-browser
    $ gcloud auth application-default login --no-launch-browser
    ```

8. If you see permission errors at runtime, then unset environment variable `GOOGLE_APPLICATION_CREDENTIALS` or add it to your BASH startup scripts (`$HOME/.bashrc` or `$HOME/.bash_profile`).
    ```bash
      unset GOOGLE_APPLICATION_CREDENTIALS
    ```

7. Set your default Google Cloud Project. Pipeline will provision instances on this project.
    ```bash
    $ gcloud config set project [YOUR_PROJECT_NAME]
    ```

# Setting up a Caper server instance

You will find [this](./conf_encode_workshop_2019.md) useful to set up your own Caper server on Google Cloud Platform.

# How to run Caper with a service account

On your Google Cloud Console, create a service account (`IAM & Admin` -> `Service Accounts`) with the following roles. You can add roles later in `IAM & Admin` -> `IAM`.
    * Service Account User
    * Compute Admin
    * Genomics Admin
    * **Cloud Life Sciences Admin** (for Cromwell's new API, i.e. `--use-google-cloud-life-sciences`)
    * Storage Admin (or set it up for an individual bucket)

Create a secret key JSON file for your service account. Make sure that your service account has enough permission for provionsing VM instances and write permission on output/work Google Cloud Storage buckets (`--gcp-out-dir` and `--gcp-work-dir`).

> **IMPORTANT**: Click on the created service account and make sure that `Enable G Suite Domain-wide Delegation` is checked to prevent the following permission error.

```
400 Bad Request
POST https://lifesciences.googleapis.com/v2beta/projects/99884963860/locations/us-central1/operations/XXXXXXXXXXXXXXXXXXXX:cancel
{
  "code" : 400,
  "errors" : [ {
    "domain" : "global",
    "message" : "Precondition check failed.",
    "reason" : "failedPrecondition"
  } ],
  "message" : "Precondition check failed.",
  "status" : "FAILED_PRECONDITION"
}
```
