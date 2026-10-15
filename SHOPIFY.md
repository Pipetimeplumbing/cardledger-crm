# Connect CardLedger to Shopify

This version supports explicit, one-way Admin GraphQL API pushes. It is not a two-way order-sync service. No store connection is configured in the repository.

## Setup

1. Obtain a Shopify app's authorized Admin API access using Shopify's supported app authentication flow. Required access includes products, inventory, and locations (`write_products`, `write_inventory`, `read_inventory`, `read_locations`; read access implied by write permissions where applicable). Install/authorize the app for your store. Follow [Shopify authentication documentation](https://shopify.dev/docs/apps/build/authentication-authorization); token acquisition and expiration depend on the app type. CardLedger does not implement OAuth or token refresh.
2. On the computer running CardLedger, configure these process environment variables before starting the program:
   - `SHOPIFY_STORE_DOMAIN`: the original `your-store.myshopify.com` hostname, without `https://` or a path.
   - `SHOPIFY_ADMIN_ACCESS_TOKEN`: a valid Admin API token. Enter it securely on your own computer; never paste it into chat, GitHub, or the public payment-link form.
   - `SHOPIFY_LOCATION_ID`: your Shopify location's numeric ID or `gid://shopify/Location/...` ID.
3. Restart CardLedger and open Manage. Shopify should say the connection is configured. This only verifies configuration presence, not successful Shopify authorization.
4. Test a single item's Shopify button in Inventory. Review the resulting draft product, SKU, price, quantity, and location in Shopify before syncing all inventory or publishing anything.

The adapter uses Admin API version `2026-07`. API compatibility, credentials, scopes, and behavior must be validated against the actual store; only simulated Shopify responses have been tested in this workspace.

## Sync behavior

- New products are created as DRAFT with stable `CL-<card id>` SKUs. Mappings are retained in your database. Existing store products are not matched or imported; first sync creates a separate CardLedger product.
- Initial creation includes the card title, category, and brand. Subsequent sync updates the mapped variant's price and selected-location quantity, not the product's title, photos, or other metadata. Price is the inventory's manually entered estimated market value, in the store's currency. CardLedger's financial reports are USD: use a USD store or implement currency conversion first.
- Quantity pushes use Shopify comparison quantities. If stock changes in Shopify since the previous sync, the push stops instead of overwriting it. This includes store orders and manual stock changes. Review those changes and record corresponding sales/restocks/removals in the CRM until the local and Shopify quantities match. Retrying then accepts the matching quantity as the new baseline. It does not guess sale prices or automatically create transactions.
- Shopify orders are not imported. Do not rely on this connector for unattended inventory control across multiple sales channels.
- Deleting a CRM listing does not delete/unpublish its Shopify product or zero out Shopify stock. Manage that product in Shopify separately.
- The full-inventory button processes current in-stock listings sequentially and stops on the first error. Use the per-item button to explicitly sync an existing zero-stock listing. Network errors may leave a partially created or updated draft; review Shopify before retrying. No automatic external rollback is possible.
- Keep a database backup. Restoring a backup can rewind mappings and stock state; inspect the store before syncing after a restore.

CSV export is also available under Manage. Shopify CSV headers and quantity handling can vary with the current importer and store locations; inspect Shopify's import preview and test a draft product before importing in bulk. CSV export has not been imported into a live store here.
