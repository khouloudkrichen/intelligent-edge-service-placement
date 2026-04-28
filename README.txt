# Pfa_Placement_System

## Setup Steps

### 1. Clone the repository

```bash
git clone <repository-url>
cd Pfa_Placement_System

2. Create virtual environment
python -m venv .venv

3. Activate virtual environment
.venv\Scripts\activate.bat

If blocked:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1

Windows CMD
.venv\Scripts\activate

4. Install dependencies
python -m pip install -r requirements.txt

-If project uses Ollama

Start Ollama first:

ollama serve

-Then run project:

python main.py