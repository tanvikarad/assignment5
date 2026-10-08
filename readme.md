Project Setup: 
Install and Configure Git

Download and install [Git for Windows](https://git-scm.com/download/win).  
Accept the default options during installation.

verify the version of git and connect to github using ssh

1. Generate a new SSH key:
ssh-keygen -t ed25519 -C "your_email@example.com"

2. Start the SSH agent:
eval "$(ssh-agent -s)"

3. Add the SSH private key to the agent:
ssh-add ~/.ssh/id_ed25519

4. Copy your SSH public key:
cat ~/.ssh/id_ed25519.pub | clip

5. Add the key to your GitHub account:
   - Go to [GitHub SSH Settings](https://github.com/settings/keys)
   - Click **New SSH Key**, paste the key, save.

6. Test the connection:
ssh -T git@github.com

You should see a success message.


3. Clone the Repository

Now you can safely clone the course project:
git clone <repository-url>
cd <repository-directory>


4. Install Python 3.10+

Download and install [Python for Windows](https://www.python.org/downloads/).  
✅ Make sure you **check the box** `Add Python to PATH` during setup.


python --version

Create and Activate a Virtual Environment (Optional but recommended)
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate.bat  # Windows


Install Required Packages
pip install -r requirements.txt


5. Running the Project
python3 main.py
