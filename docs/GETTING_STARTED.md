# Getting Started — Your First 10 Minutes

This guide walks you through setting up SupplyMind AI from scratch. If you follow the steps, you'll have the dashboard running in your browser in about 10 minutes.

**Want to try the app first?** [Open the live deployment](https://019cc876-2199-a739-4a67-dc4bb96d2042.share.connect.posit.cloud/) (Posit Connect Cloud). No installation required.

---

## What You Need Before Starting

Before you begin, make sure you have:

1. **Python 3.9 or higher**  
   The app is built with Python (the programming language that runs it). If you don't have it, download it from [python.org](https://python.org). To check if it's installed, open a terminal and type: `python --version` or `python3 --version`.

2. **A Supabase account and database**  
   Supabase is where your shipment data is stored (like a digital filing cabinet in the cloud). You'll need a project set up with the SupplyMind tables. The connection string tells the app how to reach that database.

3. **An OpenAI API key**  
   The AI uses OpenAI to predict delays and give recommendations. Think of the API key as a password that lets the app talk to OpenAI. You can get one from [platform.openai.com](https://platform.openai.com/api-keys).

---

## Installation — Step by Step

### Step 1: Download or clone the project

Get the project files onto your computer. If you're using Git:

```bash
git clone <your-repo-url>
cd supplymind-ai
```

Or download the project folder and open a terminal inside it.

---

### Step 2: Create your `.env` file

The app needs two secrets: your database connection and your OpenAI key. These go in a file called `.env`.

1. Find the file `.env.example` in the project root.
2. Copy it and name the copy `.env`.
3. Open `.env` in a text editor and fill in the values:

**Where to find the values:**

| Variable | Where to get it |
|----------|-----------------|
| `POSTGRES_CONNECTION_STRING` | Supabase Dashboard → Your project → **Project Settings** → **Database** → Copy the "Connection string" (URI). Replace `[YOUR-PASSWORD]` with your database password. |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) → Create new secret key → Copy it. |

**Example `.env`:**

```
POSTGRES_CONNECTION_STRING=postgresql://postgres:your-password@db.xxxxx.supabase.co:5432/postgres
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

Save the file and close it. Never share your `.env` file or commit it to Git.

---

### Step 3: Install dependencies

Open a terminal in the project folder and run:

```bash
pip install -r SupplyMindAI/requirements.txt
```

This installs all the libraries the app needs (Shiny, Plotly, OpenAI, and others).

---

### Step 4: Run the app

From the project root, run:

```bash
shiny run SupplyMindAI/app.py --launch-browser
```

On Windows, you can also use the run script:

```powershell
.\run.ps1
```

Your browser should open automatically and show the SupplyMind AI dashboard.

---

### Step 5: What to expect

- You should see the Supply Mind AI logo at the top.
- Below it: a **Delivery Health** section with KPI cards (Total In Transit, On Time, Delayed, Critical).
- A **Prediction Map** and sections for **Supply Chain Optimization** and simulation.

If you see all of that, you're good to go.

---

## Verifying It Works

Quick checklist:

- [ ] The dashboard loads in your browser.
- [ ] You see the Supply Mind AI logo and tagline.
- [ ] You see the Delivery Health section (may show "0" if there are no in-transit shipments in the database).
- [ ] No red error messages on the page.

If any step fails, see [Troubleshooting](TROUBLESHOOTING.md).

---

## Next Steps

- **Learn the dashboard:** [User Guide](USER_GUIDE.md)
- **Understand how each part works:** [User Guide](USER_GUIDE.md)
- **Brush up on terms:** [Glossary](GLOSSARY.md)
