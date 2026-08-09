Below is the complete logic for the **BMTB update system**, following your exact requirement:

* Version check can happen automatically.
* **No download without explicit user action.**
* Download happens in the background after the user clicks **Download Update**.
* Installation requires another explicit click.
* NSIS performs the actual application replacement.
* Previous installed BMTB version is removed.
* User data/vault is untouched.

## Python-like pseudocode

```python
# ============================================================
# BMTB AUTO UPDATE SYSTEM
# ============================================================


class AutoUpdater:

    def __init__(self, parent):
        self.parent = parent

        # ----------------------------------------------------
        # Update state
        # ----------------------------------------------------

        self.update_available = False

        self.current_version = APP_VERSION
        self.latest_version = None

        self.download_url = None
        self.release_notes = None

        self.download_path = None

        self.downloaded = False
        self.verified = False
        self.installing = False

        # ----------------------------------------------------
        # Prepare temporary update directory
        # ----------------------------------------------------

        UPDATE_DOWNLOAD_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )


    # ========================================================
    # 1. AUTOMATIC VERSION CHECK
    # ========================================================

    def check_update_background(self):

        """
        This function may be called automatically.

        IMPORTANT:
            It only checks whether an update exists.

            It MUST NOT:
                - download anything
                - launch an installer
                - close BMTB
                - install anything
        """

        start_background_thread(
            target=self._check_for_update
        )


    def _check_for_update(self):

        try:

            # ------------------------------------------------
            # Send current application information
            # ------------------------------------------------

            app_info = {
                "app_name": APP_NAME,
                "app_version": self.current_version
            }

            response = requests.post(
                UPDATE_SERVER + "/check_updates",
                json=app_info
            )

            response.raise_for_status()

            data = response.json()

            # ------------------------------------------------
            # Get server response
            # ------------------------------------------------

            self.latest_version = data.get(
                "latest_version"
            )

            self.download_url = data.get(
                "url"
            )

            self.release_notes = data.get(
                "notes"
            )

            # ------------------------------------------------
            # Compare versions
            # ------------------------------------------------

            if (
                Version(self.latest_version)
                >
                Version(self.current_version)
            ):

                self.update_available = True

                # --------------------------------------------
                # IMPORTANT:
                #
                # STOP HERE.
                #
                # DO NOT DOWNLOAD.
                # --------------------------------------------

                self.notify_update_available()

            else:

                self.update_available = False

                logging.info(
                    "BMTB is already up to date."
                )

        except Exception as error:

            logging.error(
                f"Update check failed: {error}"
            )


    # ========================================================
    # 2. NOTIFY USER
    # ========================================================

    def notify_update_available(self):

        """
        Tell the UI that an update exists.

        This does NOT download anything.
        """

        self.parent.show_update_notification(
            current_version=self.current_version,
            latest_version=self.latest_version,
            release_notes=self.release_notes
        )


    # ========================================================
    # 3. USER CLICKS "DOWNLOAD UPDATE"
    # ========================================================

    def user_requested_download(self):

        """
        THIS FUNCTION is connected to the
        "Download Update" button.

        Nothing downloads before this function
        is explicitly triggered by the user.
        """

        if not self.update_available:

            return

        if not self.download_url:

            return

        # ----------------------------------------------------
        # Prevent duplicate downloads
        # ----------------------------------------------------

        if self.is_downloading():

            return

        # ----------------------------------------------------
        # Tell UI that download is starting
        # ----------------------------------------------------

        self.parent.show_download_started()

        # ----------------------------------------------------
        # Start download in background
        # ----------------------------------------------------

        start_background_thread(
            target=self.download_update
        )


    # ========================================================
    # 4. DOWNLOAD UPDATE
    # ========================================================

    def download_update(self):

        """
        Downloads the NSIS installer.

        This function runs in a background thread.

        It does NOT install anything.
        """

        try:

            # ------------------------------------------------
            # Determine installer filename
            # ------------------------------------------------

            filename = get_filename_from_url(
                self.download_url
            )

            self.download_path = (
                UPDATE_DOWNLOAD_FOLDER
                / filename
            )

            # ------------------------------------------------
            # Start HTTP request
            # ------------------------------------------------

            response = requests.get(
                self.download_url,
                stream=True
            )

            response.raise_for_status()

            total_size = int(
                response.headers.get(
                    "content-length",
                    0
                )
            )

            downloaded_size = 0

            # ------------------------------------------------
            # Download installer
            # ------------------------------------------------

            with open(
                self.download_path,
                "wb"
            ) as installer:

                for chunk in response.iter_content(
                    chunk_size=8192
                ):

                    if not chunk:
                        continue

                    installer.write(chunk)

                    downloaded_size += len(chunk)

                    # ----------------------------------------
                    # Calculate progress
                    # ----------------------------------------

                    if total_size:

                        progress = (
                            downloaded_size
                            /
                            total_size
                        ) * 100

                        self.parent.update_download_progress(
                            progress
                        )

            # ------------------------------------------------
            # Download completed
            # ------------------------------------------------

            self.downloaded = True

            logging.info(
                "BMTB update downloaded."
            )

            # ------------------------------------------------
            # Verify installer
            # ------------------------------------------------

            self.verify_download()

        except Exception as error:

            logging.error(
                f"Update download failed: {error}"
            )

            self.downloaded = False

            self.cleanup_failed_download()

            self.parent.show_download_failed(
                str(error)
            )


    # ========================================================
    # 5. VERIFY DOWNLOADED INSTALLER
    # ========================================================

    def verify_download(self):

        """
        Verify that the downloaded installer is
        the expected file.

        Ideally the update metadata contains:

            sha256

        for the installer.
        """

        try:

            self.parent.show_verifying_update()

            expected_hash = self.get_expected_hash()

            actual_hash = calculate_sha256(
                self.download_path
            )

            # ------------------------------------------------
            # Compare hashes
            # ------------------------------------------------

            if actual_hash.lower() != expected_hash.lower():

                raise ValueError(
                    "Installer integrity verification failed."
                )

            # ------------------------------------------------
            # Verification successful
            # ------------------------------------------------

            self.verified = True

            logging.info(
                "BMTB update verified successfully."
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Still DO NOT install.
            #
            # Wait for explicit user action.
            # ------------------------------------------------

            self.parent.show_update_ready(
                self.latest_version
            )

        except Exception as error:

            self.verified = False

            logging.error(
                f"Update verification failed: {error}"
            )

            self.cleanup_failed_download()

            self.parent.show_verification_failed(
                str(error)
            )


    # ========================================================
    # 6. USER CLICKS "INSTALL UPDATE"
    # ========================================================

    def user_requested_install(self):

        """
        THIS FUNCTION is connected to the
        "Install Update" button.

        Installation cannot happen unless:

            downloaded == True
            verified == True
        """

        if not self.downloaded:

            return

        if not self.verified:

            return

        if not self.download_path.exists():

            return

        # ----------------------------------------------------
        # Ask user for final confirmation
        # ----------------------------------------------------

        confirmed = self.parent.confirm_installation(
            self.latest_version
        )

        if not confirmed:

            return

        # ----------------------------------------------------
        # Start installation
        # ----------------------------------------------------

        self.install_update()


    # ========================================================
    # 7. START NSIS INSTALLER
    # ========================================================

    def install_update(self):

        """
        Starts the downloaded NSIS installer.

        The installer is responsible for:

            - removing old application files
            - installing new application files
            - recreating shortcuts
            - updating registry information
            - preserving user data
            - launching the new BMTB
        """

        try:

            self.installing = True

            self.parent.show_installing_update()

            # ------------------------------------------------
            # Start NSIS installer
            # ------------------------------------------------

            subprocess.Popen(
                [
                    str(self.download_path)
                ]
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # BMTB must now exit.
            #
            # The installer needs BMTB to be closed
            # before replacing its files.
            # ------------------------------------------------

            self.parent.close_application()

        except Exception as error:

            self.installing = False

            logging.error(
                f"Failed to start installer: {error}"
            )

            self.parent.show_installation_failed(
                str(error)
            )


    # ========================================================
    # 8. CLEANUP
    # ========================================================

    def cleanup_failed_download(self):

        """
        Remove incomplete or invalid installers.
        """

        if (
            self.download_path
            and
            self.download_path.exists()
        ):

            try:

                self.download_path.unlink()

            except Exception as error:

                logging.error(
                    f"Cleanup failed: {error}"
                )


    # ========================================================
    # 9. OPTIONAL MANUAL UPDATE CHECK
    # ========================================================

    def manual_check_for_update(self):

        """
        Used by:

            Settings → Check for Updates

        This still ONLY checks.
        """

        self.check_update_background()
```

---

# NSIS side

The important separation is:

```python
# Python
AutoUpdater
    ↓
downloads installer
    ↓
verifies installer
    ↓
user clicks Install
    ↓
launches NSIS
    ↓
BMTB exits
```

Then NSIS takes over:

```text
NSIS Installer
│
├── Detect existing BMTB installation
│
├── Remove previous BMTB application files
│
├── Install new BMTB files
│
├── Update shortcuts
│
├── Update registry
│
├── Preserve vault/user data
│
├── Update uninstall information
│
└── Launch new BMTB
```

The exact NSIS cleanup implementation can be handled separately.

---

# ASCII flowchart

```text
                         ┌──────────────────┐
                         │   BMTB STARTS    │
                         └────────┬─────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ Automatic version check │
                    │      (background)       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │ Update available?│
                       └───────┬─────┬────┘
                               │     │
                         NO    │     │    YES
                               │     │
                               ▼     ▼
                         ┌───────┐  ┌──────────────────────┐
                         │Nothing│  │ Notify user          │
                         │happens│  │ "Update available"   │
                         └───────┘  └──────────┬───────────┘
                                               │
                                               ▼
                                  ┌────────────────────────┐
                                  │ User clicks             │
                                  │ "Download Update"       │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │ Download NSIS installer │
                                  │     (background)        │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │     Download complete   │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │   Verify SHA-256       │
                                  └───────────┬────────────┘
                                              │
                               ┌──────────────┴──────────────┐
                               │                             │
                            INVALID                        VALID
                               │                             │
                               ▼                             ▼
                       ┌────────────────┐        ┌──────────────────────┐
                       │ Delete download│        │   Update ready       │
                       │ Show failure   │        │                      │
                       └────────────────┘        │ [Install Update]     │
                                                 │ [Later]              │
                                                 └──────────┬───────────┘
                                                            │
                                                            ▼
                                                 ┌──────────────────────┐
                                                 │ User clicks           │
                                                 │ "Install Update"      │
                                                 └──────────┬───────────┘
                                                            │
                                                            ▼
                                                 ┌──────────────────────┐
                                                 │ Launch NSIS installer │
                                                 └──────────┬───────────┘
                                                            │
                                                            ▼
                                                 ┌──────────────────────┐
                                                 │      BMTB exits      │
                                                 └──────────┬───────────┘
                                                            │
                                                            ▼
                                            ┌────────────────────────────┐
                                            │       NSIS INSTALLER       │
                                            │                            │
                                            │ Remove old application    │
                                            │ Install new application   │
                                            │ Update shortcuts           │
                                            │ Update registry            │
                                            │ Preserve user/vault data  │
                                            │ Launch new BMTB            │
                                            └──────────────┬─────────────┘
                                                           │
                                                           ▼
                                                  ┌──────────────────┐
                                                  │   BMTB UPDATED   │
                                                  └──────────────────┘
```

### The critical rule

There are **three separate user/system boundaries**:

```text
AUTOMATIC
─────────
Check whether an update exists.
                 │
                 ▼
USER ACTION #1
───────────────
Download Update.
                 │
                 ▼
SYSTEM
──────
Verify download.
                 │
                 ▼
USER ACTION #2
───────────────
Install Update.
                 │
                 ▼
NSIS
────
Actually replace the application.
```

That gives you exactly the behavior you described: **BMTB can quietly know an update exists, but it never downloads or installs anything until the user explicitly tells it to.**
