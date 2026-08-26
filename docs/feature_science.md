
## Make an Api for every app for every other app to communicate with it.

Normally we should have permission from BMA to make changes to
the activities in its database because we could make mistakes that would make BMA look bad, basically.

Which means that as a convention of BM suite of apps, we must have a CLI api in order to interact with the apps' files

**For example**, if thought book wants to communicate with BMA or BMT, it has to run a subprocess or cmd calling `BMA add <list_of_POAs>` or `BMT start_timer <timer name> <timer duration in minutes>`

This means that when deploying any BM app, we must add its CLI_api.exe to system environment varibles. Specifically in `PATH`.
