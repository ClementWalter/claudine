---
name: Scaleway Deployment
description:
  This skill should be used when the user asks about "scaleway", "deploy to
  scaleway", "scaleway infrastructure", "provision scaleway", "scaleway
  terraform", "scaleway deployment", "compliant deployment", "soc2 deployment",
  "iso27001 deployment", or needs guidance on deploying applications to Scaleway
  cloud with SOC2/ISO27001 compliance baked in by design.
---

# Scaleway Deployment Skill

## Philosophy: Zero DevOps Knowledge Required

**The user doesn't know DevOps. The user doesn't WANT to know DevOps. Handle
everything.**

- Do NOT explain infrastructure concepts unless explicitly asked
- Do NOT show Terraform files, YAML configs, or command outputs unless necessary
- Ask ONLY what you absolutely cannot figure out yourself
- Store ALL credentials in GitHub Secrets once, never ask again
- Run scripts silently, only show success/failure
- When you MUST ask something, be ELI5 (Explain Like I'm 5)

## When User Says "Deploy a VPS" or "Deploy to Scaleway"

### Step 1: Ask for Server Name

Always ask: **"What do you want to call this server?"**

This name will be used for:

- The server hostname on Scaleway
- The SSH config alias (so user can `ssh root@<name>`)

### Step 2: Check if Credentials Set Up

Check if Scaleway CLI is configured: `scw config dump`

If not configured, ask for credentials ONE AT A TIME:

**Question 1: Scaleway Account**

> I need to connect to your Scaleway account. Here's how to get the keys:
>
> 1. Go to https://console.scaleway.com/iam/api-keys
> 2. Click "Generate API Key"
> 3. Copy the "Access Key" (starts with "SCW")
> 4. Copy the "Secret Key" (long random string)
>
> Paste them here (I'll store them securely in GitHub, you won't need them
> again):
>
> Access Key: Secret Key:

**Question 2: Scaleway Project**

> Now I need your Project ID:
>
> 1. Go to https://console.scaleway.com/project/settings
> 2. Copy the "Project ID" (looks like: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
>
> Paste it here:

**That's it.** Run `uv run .claude/skills/scaleway-dev/scripts/setup.py` to:

- Store credentials in GitHub Secrets
- Generate SSH keys automatically
- Create the server
- Set up everything else

Tell the user: "Setting up your server... This takes about 3 minutes."

### Step 3: Create Server and Configure SSH

After creating the server:

1. **Create non-root user** (many tools refuse to run as root):

```bash
ssh root@<IP> << 'EOF'
# Create user with sudo and docker access
useradd -m -s /bin/zsh <username>
echo "<username> ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/<username>
usermod -aG sudo,docker <username>

# Copy SSH keys
mkdir -p /home/<username>/.ssh
cp /root/.ssh/authorized_keys /home/<username>/.ssh/
chown -R <username>:<username> /home/<username>/.ssh
chmod 700 /home/<username>/.ssh
chmod 600 /home/<username>/.ssh/authorized_keys
EOF
```

Use the local username (from `whoami`) as `<username>`.

2. Add entry to `~/.ssh/config` (with non-root user):

```
Host <name>
    HostName <IP_ADDRESS>
    User <username>
    IdentityFile ~/.ssh/id_ed25519
```

3. Cache the IP: `echo "<IP>" > ~/.cache/scaleway-deploy/<name>_ip`

4. **Sync user's shell environment** (so server feels like local):

```bash
# Install zsh (as root first, before user setup)
ssh root@<IP> "apt-get install -y -qq zsh git"

# Install oh-my-zsh for the user
ssh <name> 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'

# Install common plugins
ssh <name> 'git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions; git clone https://github.com/zsh-users/zsh-syntax-highlighting ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting'

# Copy user's configs
scp ~/.zshrc <name>:~/.zshrc
scp ~/.gitconfig <name>:~/.gitconfig

# IMPORTANT: Make .zshrc portable (fix hardcoded paths and missing tools)
ssh <name> << 'FIXZSH'
# Fix hardcoded home paths
sed -i "s|/Users/[^/]*/|$HOME/|g" ~/.zshrc
sed -i "s|/opt/homebrew/[^\"]*|$HOME/.local/bin|g" ~/.zshrc

# Wrap optional tools in existence checks
sed -i 's|^\. \$HOME/.asdf/asdf.sh|[ -f "$HOME/.asdf/asdf.sh" ] \&\& . "$HOME/.asdf/asdf.sh"|' ~/.zshrc
sed -i 's|^\. "\$HOME/.atuin/bin/env"|[ -f "$HOME/.atuin/bin/env" ] \&\& . "$HOME/.atuin/bin/env"|' ~/.zshrc
sed -i 's|^eval "\$(atuin init zsh)"|command -v atuin \&>/dev/null \&\& eval "$(atuin init zsh)"|' ~/.zshrc
sed -i 's|^eval "\$(scw autocomplete script shell=zsh)"|command -v scw \&>/dev/null \&\& eval "$(scw autocomplete script shell=zsh)"|' ~/.zshrc

# Wrap nvm/load-nvmrc in existence check (comment out if nvm not installed)
if ! command -v nvm &>/dev/null; then
  sed -i '/^load-nvmrc() {/,/^}$/s/^/# /' ~/.zshrc
  sed -i 's/^add-zsh-hook chpwd load-nvmrc/# add-zsh-hook chpwd load-nvmrc/' ~/.zshrc
  sed -i '/^load-nvmrc$/s/^/# /' ~/.zshrc
fi
FIXZSH
```

6. Tell user: **"Done! Connect with: `ssh <name>`"**

### Step 4: Deploy App (if requested)

Run deployment automatically. Tell the user:

> "Deploying your app... Done! Your app is live at: http://<name> (or
> http://IP)"

## Scripts Reference (For Claude, Not User)

| Script               | Purpose                                        |
| -------------------- | ---------------------------------------------- |
| `scripts/setup.py`   | One-time setup, stores secrets in GitHub       |
| `scripts/deploy.py`  | Deploy app (use `--auto` flag for silent mode) |
| `scripts/status.py`  | Check if everything is running                 |
| `scripts/logs.py`    | Get app logs if something is wrong             |
| `scripts/destroy.py` | Tear down everything (ask for confirmation!)   |

## What To Say To Users

### On Success

> "Done! Your app is live at http://X.X.X.X"

### On Failure

> "Something went wrong. Let me check... [run logs.py, diagnose, fix > > > > > >
>
> > automatically if possible]"

### If User Asks Technical Questions

Answer briefly, then offer to just handle it:

> "That's [brief explanation]. Want me to just set it up for you?"

## Compliance (Invisible to User)

All this happens automatically, user never sees it:

- SOC2/ISO27001 controls are baked into every template
- Encrypted volumes, firewalls, audit logging - all automatic
- Compliance verification runs silently after each deploy
- If compliance fails, fix it automatically, don't bother the user

## GitHub Secrets Storage

Store these secrets in the user's GitHub repo (one time only):

| Secret Name           | Value                          |
| --------------------- | ------------------------------ |
| `SCW_ACCESS_KEY`      | Scaleway access key            |
| `SCW_SECRET_KEY`      | Scaleway secret key            |
| `SCW_PROJECT_ID`      | Scaleway project ID            |
| `SCW_SSH_PRIVATE_KEY` | Auto-generated SSH private key |
| `SCW_SSH_PUBLIC_KEY`  | Auto-generated SSH public key  |
| `SCW_SERVER_IP`       | Server IP (after provisioning) |

## Quick Commands For Claude

```bash
# Check if setup is done
uv run .claude/skills/scaleway-dev/scripts/setup.py --check

# Run full setup (interactive, asks for credentials)
uv run .claude/skills/scaleway-dev/scripts/setup.py

# Deploy (silent mode)
uv run .claude/skills/scaleway-dev/scripts/deploy.py --auto

# Check status
uv run .claude/skills/scaleway-dev/scripts/status.py

# View logs
uv run .claude/skills/scaleway-dev/scripts/logs.py --tail 50

# Destroy everything (ALWAYS ask user first!)
uv run .claude/skills/scaleway-dev/scripts/destroy.py
```

## Remember

1. **Never** show infrastructure code to the user
2. **Never** explain what Terraform/Docker/cloud-init is
3. **Never** ask about regions, instance types, or technical choices
4. **Always** use sensible defaults (fr-par, DEV1-S, Ubuntu 22.04)
5. **Always** store credentials in GitHub Secrets
6. **Always** run compliance checks silently
7. **Only** tell the user: "Setting up..." / "Deploying..." / "Done!"

## Serverless Containers (Recommended for Apps)

See the deployment strategy section above for when to use Serverless Containers vs VPS.
Quick reference: `scw container container create` and `scw container container deploy`.
