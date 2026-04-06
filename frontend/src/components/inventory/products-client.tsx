"use client";

import { useMemo, useState } from "react";
import ActionOverlay from "@/components/action-overlay";
import ConfirmActionDialog from "@/components/confirm-action-dialog";
import DataTable from "@/components/data-table";
import SectionCard from "@/components/section-card";
import StatCard from "@/components/stat-card";
import { useProductMutations, useProducts } from "@/hooks/use-products";
import type { ProductInput, ProductRow, TableColumn } from "@/lib/types";

const emptyForm: ProductInput = {
  name: "",
  description: "",
  selling_price: null,
  cost_price: null,
  stock_number: null,
  product_link: "",
  category: "",
};

const defaultCategories = [
  "Apparel",
  "Accessories",
  "Beauty",
  "Books",
  "Digital Goods",
  "Food & Beverage",
  "Health",
  "Home",
  "Office",
  "Services",
];

function formatCurrency(value: number | null) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function stockBadge(stock: number | null) {
  if ((stock ?? 0) <= 0) return "bg-red-100 text-red-700";
  if ((stock ?? 0) < 20) return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

function ProductFields({
  form,
  setForm,
  categoryOptions,
  categoryMenuOpen,
  setCategoryMenuOpen,
  addingCategory,
  setAddingCategory,
  newCategory,
  setNewCategory,
  setErrorMessage,
}: {
  form: ProductInput;
  setForm: React.Dispatch<React.SetStateAction<ProductInput>>;
  categoryOptions: string[];
  categoryMenuOpen: boolean;
  setCategoryMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  addingCategory: boolean;
  setAddingCategory: React.Dispatch<React.SetStateAction<boolean>>;
  newCategory: string;
  setNewCategory: React.Dispatch<React.SetStateAction<string>>;
  setErrorMessage: React.Dispatch<React.SetStateAction<string | null>>;
}) {
  return (
    <>
      <label className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Product name</span>
        <input
          value={form.name ?? ""}
          onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
          className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          placeholder="Product name"
        />
      </label>

      <label className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Category</span>
        <div className="relative">
          <button
            type="button"
            onClick={() => setCategoryMenuOpen((open) => !open)}
            className="flex w-full items-center justify-between rounded-xl border border-zinc-300 bg-white px-4 py-3 text-left text-sm font-normal text-zinc-900 shadow-sm transition hover:border-zinc-400 hover:shadow-md"
          >
            <span className={form.category ? "text-zinc-900" : "text-zinc-500"}>{form.category || "Select a category"}</span>
            <span className="text-xs text-zinc-500">▾</span>
          </button>

          {categoryMenuOpen ? (
            <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_24px_60px_-24px_rgba(15,23,42,0.35)]">
              <div className="border-b border-zinc-100 px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Categories</div>
              <div className="max-h-72 overflow-y-auto p-2">
                {categoryOptions.map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => {
                      setForm((current) => ({ ...current, category }));
                      setCategoryMenuOpen(false);
                      setAddingCategory(false);
                      setNewCategory("");
                      setErrorMessage(null);
                    }}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${form.category === category ? "bg-zinc-900 text-white" : "text-zinc-700 hover:bg-zinc-100"}`}
                  >
                    <span>{category}</span>
                    {form.category === category ? <span>✓</span> : null}
                  </button>
                ))}
              </div>
              <div className="border-t border-zinc-100 bg-zinc-50/70 p-2">
                {!addingCategory ? (
                  <button
                    type="button"
                    onClick={() => {
                      setAddingCategory(true);
                      setNewCategory("");
                    }}
                    className="flex w-full items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-3 text-sm font-medium text-zinc-700 transition hover:border-zinc-400 hover:bg-zinc-50"
                  >
                    + Add new category
                  </button>
                ) : (
                  <div className="space-y-2 rounded-xl bg-white p-2">
                    <input
                      value={newCategory}
                      onChange={(event) => setNewCategory(event.target.value)}
                      className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm font-normal"
                      placeholder="Add a new category"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const trimmed = newCategory.trim();
                          if (!trimmed) {
                            setErrorMessage("Category name is required.");
                            return;
                          }
                          setForm((current) => ({ ...current, category: trimmed }));
                          setAddingCategory(false);
                          setNewCategory("");
                          setCategoryMenuOpen(false);
                          setErrorMessage(null);
                        }}
                        className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white"
                      >
                        Save category
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setAddingCategory(false);
                          setNewCategory("");
                        }}
                        className="rounded-xl border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </label>

      <label className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Selling price (customer-facing, USD)</span>
        <input
          value={form.selling_price ?? ""}
          onChange={(event) => setForm((current) => ({ ...current, selling_price: event.target.value === "" ? null : Number(event.target.value) }))}
          className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          type="number"
          min="0"
          step="0.01"
        />
      </label>

      <label className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Cost price (internal, USD)</span>
        <input
          value={form.cost_price ?? ""}
          onChange={(event) => setForm((current) => ({ ...current, cost_price: event.target.value === "" ? null : Number(event.target.value) }))}
          className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          type="number"
          min="0"
          step="0.01"
        />
      </label>

      <label className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Product link</span>
        <input
          value={form.product_link ?? ""}
          onChange={(event) => setForm((current) => ({ ...current, product_link: event.target.value }))}
          className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          placeholder="Product link"
        />
      </label>

      <div className="space-y-2 text-sm font-medium text-zinc-700">
        <span>Stock number (units on hand)</span>
        <div className="flex items-center gap-3 rounded-xl border border-zinc-300 bg-zinc-50 px-3 py-3">
          <button
            type="button"
            onClick={() => setForm((current) => ({ ...current, stock_number: Math.max(0, (current.stock_number ?? 0) - 1) }))}
            className="h-10 w-10 rounded-full border border-zinc-300 bg-white text-lg text-zinc-700"
          >
            −
          </button>
          <input
            value={form.stock_number ?? 0}
            onChange={(event) => {
              const nextValue = event.target.value;
              setForm((current) => ({
                ...current,
                stock_number: nextValue === "" ? 0 : Math.max(0, Number(nextValue)),
              }));
            }}
            className="min-w-20 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-center text-lg font-semibold text-zinc-900"
            type="number"
            min="0"
          />
          <button
            type="button"
            onClick={() => setForm((current) => ({ ...current, stock_number: (current.stock_number ?? 0) + 1 }))}
            className="h-10 w-10 rounded-full border border-zinc-300 bg-white text-lg text-zinc-700"
          >
            +
          </button>
        </div>
      </div>

      <label className="md:col-span-2 space-y-2 text-sm font-medium text-zinc-700">
        <span>Product description</span>
        <textarea
          value={form.description ?? ""}
          onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
          className="min-h-28 w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
          placeholder="Product description"
        />
      </label>
    </>
  );
}

export default function ProductsClient({ initialData }: { initialData: ProductRow[] }) {
  const { data, isLoading, isError } = useProducts(initialData);
  const { createProduct, updateProduct, deleteProduct, isCreating, isUpdating, isDeleting } = useProductMutations();
  const [form, setForm] = useState<ProductInput>(emptyForm);
  const [selectedProduct, setSelectedProduct] = useState<ProductRow | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<"save" | "delete" | null>(null);
  const [addingCategory, setAddingCategory] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [categoryMenuOpen, setCategoryMenuOpen] = useState(false);
  const [showEditOverlay, setShowEditOverlay] = useState(false);

  const categoryOptions = useMemo(
    () => Array.from(new Set([...defaultCategories, ...data.map((item) => item.category).filter((value): value is string => Boolean(value?.trim()))])).sort(),
    [data]
  );

  const stats = useMemo(() => {
    const totalProducts = data.length;
    const lowStock = data.filter((item) => (item.stock_number ?? 0) < 20).length;
    const unitsOnHand = data.reduce((sum, item) => sum + (item.stock_number ?? 0), 0);
    return [
      { title: "Products", value: String(totalProducts), description: "Active catalog items" },
      { title: "Low Stock", value: String(lowStock), description: "Items below 20 units" },
      { title: "Units on Hand", value: String(unitsOnHand), description: "Total inventory available" },
    ];
  }, [data]);

  const columns: TableColumn<ProductRow>[] = [
    { key: "name", label: "Product" },
    { key: "category", label: "Category" },
    { key: "selling_price", label: "Price", render: (value) => formatCurrency((value as number | null) ?? null) },
    {
      key: "stock_number",
      label: "Stock",
      render: (value) => <span className={`rounded-full px-3 py-1 text-xs font-medium ${stockBadge((value as number | null) ?? null)}`}>{(value as number | null) ?? 0}</span>,
    },
    {
      key: "actions",
      label: "Actions",
      render: (_, row) => (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setSelectedProduct(row);
              setForm({
                name: row.name,
                description: row.description,
                selling_price: row.selling_price,
                cost_price: row.cost_price,
                stock_number: row.stock_number,
                product_link: row.product_link,
                category: row.category,
              });
              setCategoryMenuOpen(false);
              setAddingCategory(false);
              setNewCategory("");
              setShowCreateForm(false);
              setShowEditOverlay(true);
              setErrorMessage(null);
            }}
            className="rounded-lg border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700"
          >
            Edit
          </button>
          <button
            onClick={() => {
              setSelectedProduct(row);
              setConfirmAction("delete");
              setErrorMessage(null);
            }}
            className="rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-700"
          >
            Delete
          </button>
        </div>
      ),
    },
  ];

  async function runConfirmedProductAction() {
    setErrorMessage(null);
    try {
      if (confirmAction === "save") {
        if (!form.name?.trim()) throw new Error("Product name is required.");
        if (!form.category?.trim()) throw new Error("Product category is required.");
        if (form.selling_price === null || form.selling_price === undefined || form.selling_price <= 0) throw new Error("Selling price must be greater than 0.");
        if (form.cost_price === null || form.cost_price === undefined || form.cost_price < 0) throw new Error("Cost price must be 0 or greater.");
        if (form.stock_number === null || form.stock_number === undefined || form.stock_number < 0) throw new Error("Stock number must be 0 or greater.");

        if (selectedProduct) {
          await updateProduct(selectedProduct.id, form);
          setShowEditOverlay(false);
        } else {
          await createProduct(form);
          setShowCreateForm(false);
        }

        setSelectedProduct(null);
        setForm(emptyForm);
        setAddingCategory(false);
        setNewCategory("");
        setCategoryMenuOpen(false);
      }

      if (confirmAction === "delete") {
        if (!selectedProduct) throw new Error("Select a product first.");
        await deleteProduct(selectedProduct.id);
        setSelectedProduct(null);
        setShowEditOverlay(false);
      }

      setConfirmAction(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save product.");
      setConfirmAction(null);
    }
  }

  function handleSubmitProduct(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConfirmAction("save");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Products & Inventory</h1>
        <p className="mt-2 text-zinc-500">Manage your catalog, keep stock current, and spot low-inventory items before they block sales.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => <StatCard key={stat.title} title={stat.title} value={stat.value} description={stat.description} />)}
      </div>

      {isError ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to load product inventory.</p> : null}
      {errorMessage ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</p> : null}

      {!selectedProduct && !showCreateForm && !showEditOverlay ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setShowCreateForm(true);
              setSelectedProduct(null);
              setForm(emptyForm);
              setAddingCategory(false);
              setNewCategory("");
              setCategoryMenuOpen(false);
              setErrorMessage(null);
            }}
            className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white"
          >
            Add product
          </button>
        </div>
      ) : null}

      {showCreateForm ? (
        <SectionCard title="Add Product" description="Create a new catalog item, then confirm it before saving.">
          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmitProduct}>
            <ProductFields
              form={form}
              setForm={setForm}
              categoryOptions={categoryOptions}
              categoryMenuOpen={categoryMenuOpen}
              setCategoryMenuOpen={setCategoryMenuOpen}
              addingCategory={addingCategory}
              setAddingCategory={setAddingCategory}
              newCategory={newCategory}
              setNewCategory={setNewCategory}
              setErrorMessage={setErrorMessage}
            />
            <div className="md:col-span-2 flex flex-wrap gap-3">
              <button type="submit" disabled={isCreating} className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">Review new product</button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  setForm(emptyForm);
                  setAddingCategory(false);
                  setNewCategory("");
                  setCategoryMenuOpen(false);
                  setErrorMessage(null);
                }}
                className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
              >
                Cancel add
              </button>
            </div>
          </form>
        </SectionCard>
      ) : null}

      <SectionCard title="Catalog" description="Browse products, pricing, and current stock levels.">
        {isLoading ? <p className="text-sm text-zinc-500">Loading products...</p> : <DataTable columns={columns} data={data} />}
      </SectionCard>

      <ActionOverlay
        open={showEditOverlay && Boolean(selectedProduct)}
        title={selectedProduct ? `Edit ${selectedProduct.name}` : "Edit product"}
        description="Adjust the current information, then review the changes before saving."
        onCloseAction={() => {
          setShowEditOverlay(false);
          setSelectedProduct(null);
          setForm(emptyForm);
        }}
      >
        <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmitProduct}>
          <ProductFields
            form={form}
            setForm={setForm}
            categoryOptions={categoryOptions}
            categoryMenuOpen={categoryMenuOpen}
            setCategoryMenuOpen={setCategoryMenuOpen}
            addingCategory={addingCategory}
            setAddingCategory={setAddingCategory}
            newCategory={newCategory}
            setNewCategory={setNewCategory}
            setErrorMessage={setErrorMessage}
          />
          <div className="md:col-span-2 flex flex-wrap gap-3">
            <button type="submit" disabled={isUpdating} className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">Review changes</button>
            <button
              type="button"
              onClick={() => {
                setShowEditOverlay(false);
                setSelectedProduct(null);
                setForm(emptyForm);
              }}
              className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
            >
              Cancel
            </button>
          </div>
        </form>
      </ActionOverlay>

      <ConfirmActionDialog
        open={Boolean(confirmAction)}
        title={confirmAction === "delete" ? `Confirm delete for ${selectedProduct?.name ?? "product"}` : selectedProduct ? `Confirm update for ${selectedProduct.name}` : "Confirm new product"}
        description={confirmAction === "delete" ? "Delete this product now?" : selectedProduct ? "Save these product edits now?" : "Create this product now?"}
        confirmLabel={confirmAction === "delete" ? "Confirm delete" : selectedProduct ? "Confirm update" : "Confirm create"}
        loading={isCreating || isUpdating || isDeleting}
        onCancelAction={() => setConfirmAction(null)}
        onConfirmAction={runConfirmedProductAction}
      />
    </div>
  );
}
