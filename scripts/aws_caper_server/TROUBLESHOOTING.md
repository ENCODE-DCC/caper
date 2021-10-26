## Troubleshooting

Run `caper debug WORKFLOW_ID` to debug/troubleshoot a workflow.






### `Could not read from s3...`


If you use private S3 URIs in an input JSON then you will see this error. Please don't use any private S3 URIs. Get a presigned HTTP URL of the private bucket file or use `~/.netrc` authentication instead.

```javascript
"failures": [
    {
        "causedBy": [
            {
                "causedBy": [
                    {
                        "message": "s3://s3.amazonaws.com/encode-processing/test_without_size_call/5826859d-d07c-4749-a2fe-802c6c6964a6/call-get_b/get_b-rc.txt",
                        "causedBy": []
                    }
                ],
                "message": "Could not read from s3://encode-processing/test_without_size_call/5826859d-d07c-4749-a2fe-802c6c6964a6/call-get_b/get_b-rc.txt: s3://s3.amazonaws.com/encode-processing/test_without_size_call/5826859d-d07c-4749-a2fe-802c6c6964a6/call-get_b/get_b-rc.txt"
            }
        ],
        "message": "[Attempted 1 time(s)] - IOException: Could not read from s3://encode-processing/test_without_size_call/5826859d-d07c-4749-a2fe-802c6c6964a6/call-get_b/get_b-rc.txt: s3://s3.amazonaws.com/encode-processing/test_without_size_call/5826859d-d07c-4749-a2fe-802c6c6964a6/call-get_b/get_b-rc.txt"
    }
],
```

If you still see this error, then please try with the `priority` queue instead of `default` queue. Go to AWS Batch on your AWS Console and click on Job Queues. Get ARN of the `priority-*` queue and define it for `aws-batch-arn=` in your Caper conf (`~/.caper/default.conf`). The `default` queue is based on spot instances and they seem to be interrupted quite often and Cromwell doesn't handle it properly.



### `S3Exception: null (Service: S3, Status Code: 301)`

If you use S3 URIs in an input JSON which are in a different region, then you will see `301 Error`. Please don't use S3 URIs out of your region. It's better to

```javascript
"callCaching": {
    "hashFailures": [
        {
            "causedBy": [
                {
                    "message": "null (Service: S3, Status Code: 301, Request ID: null, Extended Request ID: MpqH6PrTGZwXu2x5pt8H38VWqnrpWWT7nzH/fZtbiEIKJkN9qrB2koEXlmXAYdvehvAfy5yQggE=)",
                    "causedBy": []
                }
            ],
            "message": "[Attempted 1 time(s)] - S3Exception: null (Service: S3, Status Code: 301, Request ID: null, Extended Request ID: MpqH6PrTGZwXu2x5pt8H38VWqnrpWWT7nzH/fZtbiEIKJkN9qrB2koEXlmXAYdvehvAfy5yQggE=)"
        }
    ],
    "allowResultReuse": false,
    "hit": false,
    "result": "Cache Miss",
    "effectiveCallCachingMode": "CallCachingOff"
}
```


### `S3Exception: null (Service: S3, Status Code: 400)`

If you see `400` error then please use this shell script `./create_instance.sh` to create an instance instead of running Caper server on your laptop/machine.


### Tasks (jobs) are stuck at RUNNABLE status

Go to `Job Queues` in `AWS Batch` on your AWS console and find your job queue (default or priority) that matches with the ARN in your Caper conf. Edit the queue and increase number of maximum vCPUs.
