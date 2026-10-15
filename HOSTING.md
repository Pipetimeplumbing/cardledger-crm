# Private owner login and $5/month customer accounts

## Owner-only Render deployment

Connect the `Pipetimeplumbing/cardledger-crm` GitHub repository to a NEW Render Python Web Service. This is separate from the plumbing service.

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 16 --timeout 120`
- Health check: `/health`
- Attach a persistent disk at `/var/data` on a compatible paid plan. Review current pricing before creating it.
- Environment: `DATABASE_PATH=/var/data/collection.sqlite`
- Set `OWNER_EMAIL` and a strong `OWNER_PASSWORD` (12–128 characters) securely in Render settings. Never put them in chat or GitHub.
- Keep `ENABLE_SIGNUP=false` while only you use the app.

Owner credentials are created only when no owner exists, and never overwritten at restart. After first successful setup, remove `OWNER_PASSWORD` from environment settings. To reset it from a trusted Render shell, run `python setup_owner.py --reset`. The owner receives the original inventory database. For existing local records, stop the local app, make a backup, and transfer the entire data directory securely before initializing hosted accounts. Do not upload customer databases to GitHub.

Accounts and sessions live in `/var/data/accounts.sqlite`. Each customer workspace has its own `/var/data/workspaces/<account id>/collection.sqlite`. Preserve and back up the ENTIRE data directory, not just collection.sqlite. In-app backups export only the signed-in account's inventory, not the central accounts/subscriptions database. Configure managed disk snapshots plus an independently stored backup before real customer use. Restoring old billing data requires reconciling current Stripe subscription status.

The local backend can still run on your own computer, but now requires owner setup. Run **Setup Owner.bat** once after installing the update. Your original inventory stays assigned to the owner.

## Enable customer subscriptions

The configured price is **$5 USD every month**. Your owner login is exempt. Stripe handles hosted checkout and payment information; CardLedger does not store card numbers.

1. Create a CardLedger product and a recurring monthly **$5.00 USD** price in your Stripe account. Use test mode first. This is separate from card-sale payment links and the plumbing business's payment link.
2. In Render securely configure `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, and `APP_BASE_URL=https://YOUR-CARDLEDGER-SERVICE.onrender.com`. Never commit credentials.
3. Create a Stripe webhook at `https://YOUR-CARDLEDGER-SERVICE.onrender.com/api/billing/webhook`, subscribing to `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, and `invoice.payment_failed`.
4. Enable Stripe's customer billing portal with subscription cancellation and payment-method updates. Avoid enabling arbitrary plan changes until supported.
5. Test new account creation, monthly checkout, delayed webhook delivery, renewals, failed payments, cancellation, and billing-portal access. Only then set `ENABLE_SIGNUP=true`. New accounts are inactive and cannot read or write inventory until a signed webhook confirms an eligible active/trialing subscription.
6. Use matching Stripe live-mode keys, webhook signing secret, and price when ready to charge real customers. No live charges or subscription products were created in this coding session.

Checkout success redirects do NOT grant access. Webhooks verify signatures and timestamp freshness, ignore previously processed event IDs, and fetch current Stripe subscriptions to handle out-of-order event delivery. Canceled-at-period-end subscriptions stay accessible while Stripe reports them active. Inactive/past-due accounts lose workspace access but retain account and billing-portal access. Data is retained for possible reactivation.

## Before selling subscriptions publicly

- Complete privacy policy, terms, support contact, refund/cancellation policies, and appropriate tax setup. No paid public signup is enabled by default.
- Add email verification and automated password-recovery email. Password change is available while signed in; recovery currently requires trusted operator assistance.
- Validate production HTTPS, backups/restoration, monitoring, and multi-account isolation on your actual host.
- Load-test before expanding beyond a small pilot. This version uses per-workspace SQLite and one process with threaded event streams; it is not a tested high-scale SaaS platform. Each live browser tab consumes a worker thread while connected. Use a suitable database/event architecture before scaling.
- Shopify connection credentials are currently owner-only, so subscriber workspaces cannot access the owner's store. Per-customer Shopify OAuth is not implemented.
- Subscription logic has automated tests using simulated Stripe API responses. Live Stripe checkout/webhooks and Render hosting have not been verified in this session.

## Protection

Passwords are scrypt hashes. Opaque 24-hour sessions are stored as token hashes with HttpOnly, SameSite=Lax cookies; hosted cookies require HTTPS. Browser mutations require same-origin JSON. Authentication is rate-limited. Workspace routes, receipts, CSVs, payment settings, and backups are gated by account and subscription. No first-visitor owner registration is exposed publicly.
