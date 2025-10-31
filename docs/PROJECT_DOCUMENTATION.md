# Thought Book Documentation

## Overview

**Thought Book** is a fast, offline-first, and private note-taking application for Windows. It is designed to provide users with a secure, modern, and easy-to-use space to capture and manage their thoughts without relying on the internet or cloud services. The app emphasizes privacy, simplicity, and speed, making it ideal for users who want instant access to their notes and complete control over their data.

## Features

- **Local Storage & Encryption:** All notes are stored locally in an encrypted SQLite database. No data is sent to the cloud by default.
- **Password Protection & Recovery:** Users set a password and a recovery code to protect access to their notes. Passwords are securely hashed.
- **Modern UI:** Built with CustomTkinter, the app offers a clean, intuitive interface with sidebar navigation and auto-save functionality.
- **Freemium Model:** Free users can create up to 5 notes. Premium users unlock unlimited notes and additional features by purchasing a license key.
- **Installer & Shortcuts:** The project includes scripts to build a Windows installer and create desktop/start menu shortcuts with a global hotkey for quick access.
- **Feedback & Licensing:** Integrated feedback system allows users to send suggestions or bug reports. License management enables premium upgrades.
- **Optional Backup:** Users can back up their notes to Google Drive or other locations, with step-by-step instructions provided.
- **Auto-Updater:** The app can check for updates and install new versions automatically.

## Project Structure

```
thought_book/
├── deploy.py                # Deployment script (builds installer)
├── note_app.py              # Main application source code
├── scripts/                 # Core modules (database, encryption, settings, etc.)
├── imgs/                    # Icons and images
├── docs/                    # Documentation files
├── requirements.txt         # Python dependencies
├── LICENSE                  # License information
├── README.md                # Project summary
```

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Tech-Naija-Rise/thought_book.git
   cd thought_book
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Build and run the app:**
   - Run `python deploy.py` to build the installer and create shortcuts.
   - Or run `python main.py` directly for development.

## Usage

- On first launch, set your password and recovery code.
- Create, edit, and delete notes using the sidebar and editor.
- Use the settings window to manage password, clear notes, and provide feedback.
- Upgrade to premium for unlimited notes and advanced features.
- Backup your notes by following the instructions in `docs/how_to.md`.

## Contributing

We welcome contributions to Thought Book! Here’s how you can help:

### 1. Fork & Clone
- Fork the repository on GitHub.
- Clone your fork locally:
  ```bash
  git clone https://github.com/<your-username>/thought_book.git
  ```

### 2. Set Up Your Environment
- Install Python 3.8+ and all dependencies from `requirements.txt`.
- Test your changes locally before submitting.

### 3. Make Changes
- Add new features, fix bugs, or improve documentation.
- Follow the existing code style and structure.
- Write clear commit messages.

### 4. Test
- Ensure your changes do not break existing functionality.
- Run the app and verify new features or fixes.

### 5. Submit a Pull Request
- Push your changes to your fork.
- Open a pull request to the `main` branch of the original repository.
- Describe your changes and reference any related issues.

### 6. Review & Feedback
- The maintainers will review your PR and may request changes.
- Respond to feedback and update your PR as needed.

### 7. Code of Conduct
- Be respectful and constructive in all communications.
- Do not submit malicious code or violate user privacy.

## Reporting Issues

- Use the GitHub Issues page to report bugs, request features, or ask questions.
- Provide clear steps to reproduce bugs and include screenshots if possible.

## License

This project is licensed for personal use and contributions. Commercial use or redistribution is prohibited without explicit permission. See `LICENSE` for details.

## Contact

For questions, feedback, or support, use the feedback feature in the app or open an issue on GitHub.

---

For more details on specific features, backup instructions, and advanced usage, see the other documentation files in the `docs/` folder.
