# Building Personal Tools: A Guide to Simple, Effective Software for Personal Use

## Why Build Personal Tools?

The best software you'll ever use might be something you build for yourself. Not because it's technically impressive or feature-complete, but because it solves *your* specific problem in *your* preferred way. Historically, these would be shell scripts you painstakingly cobbled together that only works on that old thinkpad running a specific version of Linux. Today, with the advent of Generative AI and accessible cloud infrastructure, building portable personal tools has never been easier or more rewarding.

Personal tools don't need to scale to millions of users. They don't need extensive documentation, internationalization, or comprehensive test coverage. They just need to work for you, right now, for the problem you're facing. GenAI has made it easier than ever to build these, and you should take advantage of that.

## General Principles

**Build for immediate needs, not hypothetical ones.**

When you encounter a repetitive task or friction in your workflow, that's your signal. Don't plan a grand architecture. Don't overthink it. Just build the smallest thing that removes that friction.

**Iteration happens naturally.**

You'll use your tool. You'll notice what's missing. You'll add it. This organic growth produces better software than upfront planning ever could, because it's guided by real usage rather than speculation. Iteration and customization is an ssh command away.

## The Stack Doesn't Matter Much

Use what you know. Python is god's pseudocode, use it. If you love JavaScript, use that. The "best" stack is the one you can ship with today.

That said, some choices do reduce friction:

- **Simple frameworks over complex ones**: FastHTML, Flask, Express—frameworks that let you go from idea to running code in minutes, not hours.
- **SQLite over PostgreSQL**: Unless you need concurrent writes or multi-gigabyte datasets, SQLite is simpler to deploy and reason about.
- **Forms over SPAs**: HTML forms are stateless, require no client-side JavaScript, and work everywhere. Start there.
- **Monoliths over microservices**: You're one person. One codebase is enough.

## Hosting on a VPS

Cloud platforms are great for scalability, but for personal tools, a simple VPS offers clarity:

- **Fixed cost**: $5-10/month, regardless of usage. It is a raspberry pi in someone's shed.
- **Full control**: Install what you want, run what you need. It runs ubuntu; ssh in, run tmux, run your applications in tmux panes and they will persist.
- **Simplicity**: No IAM policies, no service quotas, no surprise bills
- **SSH access**: Direct access to debug, inspect, and modify. Everything is a terminal command away, and you don't need to stitch together multiple services with opaque prices, APIs, and UIs.

Pick any provider (Hetzner, DigitalOcean, Linode, Vultr—they're all fine). Get the cheapest tier. You won't outgrow it. Follow [this](https://bhargav.dev/blog/VPS_Setup_and_Security_Checklist_A_Complete_Self_Hosting_Guide) for a crash course in VPS setup and security.

### The Setup Pattern

1. **Nginx as a reverse proxy**: One web server, multiple apps on different paths
2. **Port-per-app**: Each tool runs on its own port (8001, 8002, etc.)
3. **Process management**: Simple background processes or systemd services
4. **SSL with Let's Encrypt**: `certbot` makes HTTPS trivial

This pattern scales from 1 to 20+ small apps without additional complexity.

You can (optionally) buy a domain and point it to your VPS. Use subdomains or paths for different tools. Then again, IP addresses work fine too, and are cryptic enough to deter casual snooping.

## Examples from Practice


I ssh onto my VPS with port forwarding like so (in `~/.ssh/config`):

```
Host myvps
    HostName <ip_address>
    User myuser
    LocalForward 8001 localhost:8001
```

and then run the apps locally on the port i've forwarded for prototyping and testing. When I'm happy, I run them on the VPS by starting them in a tmux session in a port specific to each app, and update `nginx.conf` (which itself is symlinks to `/etc/nginx/sites-enabled/`) to point to the right port.

I've built a few personal tools following this approach:

- **[Radio](https://lalten.org/radio)**: A web-based radio player for streaming stations. No playlists, no accounts—just URLs and play buttons.
- **[LinkPull](https://lalten.org/linkpull)**: Scrapes URLs from webpages with regex filtering. Built because I kept needing to download specific file types from index pages.

Both are under 300 lines of code (largely vibecoded for the prototype and debugged with iteration).
Both solve real problems I had. Neither required more than a couple of hours to build. They run on my phone, computer, and on the devices of friends and family.

There are also a couple of CRUD apps for things like shopping lists and meal planning that are automatically synced across users because they're hosted on the VPS and accessible via web. Obviously don't host sensitive data without proper security, but for low-stakes stuff, it's fine; I'd rather have you know that I need granola than have to engineer an entire auth system.

## The Real Value

Personal tools teach you more than tutorials ever could. You make real choices. You see what matters and what doesn't. You learn to ship, get feedback from your own use or your friends' and family's, and iterate.

They also compound. Once you have the infrastructure (VPS, nginx, domain), adding a new tool is trivial. The marginal cost approaches zero.

Most importantly, you build software on your terms. No product managers, no sprint planning, no stakeholder alignment. Just you, a problem, and a solution.

## Start Small

Don't build a platform. Don't build infrastructure. Don't even build a "system."
Build one small tool that solves one annoying problem you have today.
Then use it.
Stop larping as the 'founder' or 'builder' of some hammer in search of a nail. Just build the damn hammer for the nail you have right now, and if you need another screwdriver later, build that too.
