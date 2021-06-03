## Troubleshooting errors

If you see permission errors check if the above roles are correctly configured for your service account.

If you see PAPI errors and Google's HTTP endpoint deprecation warning. Remove Life Sciences API role from your service account and add it back.

If you see the following error then click on your service account on `Service Account` in `IAM` of your Google project and make sure that `Enable G Suite Domain-wide Delegation` is checked.
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
