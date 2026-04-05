# Owner QA Report

## Scope

Authenticated browser QA on `http://localhost:3000` using the provided owner account.

Routes covered:

- `/login`
- `/dashboard`
- `/pending-approvals`
- `/daily-digest`
- `/memory`
- `/operations/products`
- `/roles/customers`
- `/roles/suppliers`
- `/roles/investors`
- `/roles/partners`

## Verified flows

### Authentication

- Login succeeds and redirects into the protected app.
- Protected routes remain guarded when unauthenticated.

### Products & inventory

- Product creation works with required validation.
- Category selection supports built-in categories plus custom category creation.
- Product rows render after creation.

### Stakeholder management

- Customer creation works after API id fix.
- Role switching from customer to investor works and creates the destination role record.
- Protected stakeholder APIs remain auth-guarded.

## Issues found during QA

### Fixed

1. **Stakeholder create API failed with null id**
   - Symptom: `null value in column "id"` on `/api/roles/customers`
   - Fix: explicit UUID generation on stakeholder create and role-switch target insert.

2. **Duplicate React key errors in stakeholder tables**
   - Symptom: console errors about duplicate `id` keys.
   - Fix: unique virtual keys for detail/actions columns plus more tolerant table rendering.

3. **Product create API failed with null id**
   - Symptom: `null value in column "id"` on `/api/products`
   - Fix: explicit UUID generation on create.

4. **Product form allowed ambiguous or under-specified data**
   - Symptom: blank intent around numeric fields and incomplete create validation.
   - Fix: required validation for name/category/selling price/cost price/stock number, clearer labels, blank numeric start state.

5. **Category add flow was clumsy**
   - Symptom: add action sat outside the selector.
   - Fix: custom dropdown with in-panel add-category action and reusable general categories.

6. **Create forms cluttered list pages**
   - Symptom: add forms always consumed vertical space.
   - Fix: forms now open only after clicking Add above the table.

### Remaining owner-perspective improvement areas

1. **Dashboard depth is still shallow**
   - Owner need: clearer operational summaries for sales, stock movement, and review/audit history.

2. **Role switching should surface post-action confirmation state better**
   - Owner need: clearer “source archived / destination active” messaging after a switch.

3. **Empty states are still too plain**
   - Owner need: stronger guidance on what to do next when there is no digest, no memory, or no approvals.

4. **Shell and cards were visually flat**
   - Improvement applied: added stronger accenting, warmer background treatment, and better navigation emphasis.

## Owner-facing design improvements applied

- Added more color and contrast to the shell and stat cards.
- Improved sidebar active state and shell hierarchy.
- Softened section card styling for a more intentional admin feel.
- Added category dropdown styling and richer interaction affordance.

## QA outcome

- Protected route access: **Pass**
- Product create flow: **Pass**
- Customer create flow: **Pass**
- Customer → investor role switch: **Pass**
- Console stability after fixes: **Pass**
