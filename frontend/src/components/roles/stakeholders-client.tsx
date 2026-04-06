"use client";

import { useMemo, useState } from "react";
import ActionOverlay from "@/components/action-overlay";
import ConfirmActionDialog from "@/components/confirm-action-dialog";
import DataTable from "@/components/data-table";
import SectionCard from "@/components/section-card";
import { useStakeholderMutations, useStakeholders } from "@/hooks/use-stakeholders";
import { stakeholderFieldLabels, switchTargetOptions, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderInput, StakeholderRow, TableColumn } from "@/lib/types";

type ConfirmState =
  | { type: "create" }
  | { type: "edit"; row: StakeholderRow }
  | { type: "delete"; row: StakeholderRow }
  | { type: "switch"; row: StakeholderRow; targetRole: StakeholderRole }
  | null;

function emptyForm(role: StakeholderRole): StakeholderInput {
  return {
    name: "",
    email: "",
    phone: "",
    status: "active",
    company: role === "customers" ? "" : undefined,
    preference: role === "customers" ? "" : undefined,
    category: role === "suppliers" ? "" : undefined,
    contract_notes: role === "suppliers" ? "" : undefined,
    focus: role === "investors" ? "" : undefined,
    partner_type: role === "partners" ? "" : undefined,
    notes: role === "investors" || role === "partners" || role === "customers" ? "" : undefined,
  };
}

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function StakeholderFields({
  fieldSet,
  form,
  setForm,
}: {
  fieldSet: Array<{ key: string; label: string }>;
  form: StakeholderInput;
  setForm: React.Dispatch<React.SetStateAction<StakeholderInput>>;
}) {
  return (
    <>
      {fieldSet.map((field) =>
        field.key === "notes" || field.key === "contract_notes" ? (
          <label key={field.key} className="md:col-span-2 space-y-2 text-sm font-medium text-zinc-700">
            <span>{field.label}</span>
            <textarea
              value={(form[field.key as keyof StakeholderInput] as string | null | undefined) ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
              className="min-h-28 w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
            />
          </label>
        ) : (
          <label key={field.key} className="space-y-2 text-sm font-medium text-zinc-700">
            <span>{field.label}</span>
            <input
              value={(form[field.key as keyof StakeholderInput] as string | null | undefined) ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
              className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
            />
          </label>
        )
      )}
    </>
  );
}

export default function StakeholdersClient({
  role,
  title,
  description,
  initialData,
}: {
  role: StakeholderRole;
  title: string;
  description: string;
  initialData: StakeholderRow[];
}) {
  const { data, isLoading, isError } = useStakeholders(role, initialData);
  const { createStakeholder, updateStakeholder, deleteStakeholder, switchStakeholder, isCreating, isUpdating, isDeleting, isSwitching } =
    useStakeholderMutations(role);
  const [form, setForm] = useState<StakeholderInput>(emptyForm(role));
  const [selectedRow, setSelectedRow] = useState<StakeholderRow | null>(null);
  const [switchRole, setSwitchRole] = useState<StakeholderRole>(switchTargetOptions[role][0]);
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [overlayMode, setOverlayMode] = useState<"edit" | "switch" | null>(null);

  const fieldSet = stakeholderFieldLabels[role];

  const columns = useMemo<TableColumn<StakeholderRow>[]>(() => {
    const primaryColumns: TableColumn<StakeholderRow>[] = [
      { key: "name", label: "Name" },
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
      {
        key: "detail",
        label:
          role === "customers"
            ? "Company"
            : role === "suppliers"
              ? "Category"
              : role === "investors"
                ? "Focus"
                : "Partner Type",
        render: (_, row) => {
          if (row.role === "customers") return row.company ?? "—";
          if (row.role === "suppliers") return row.category ?? "—";
          if (row.role === "investors") return row.focus ?? "—";
          return row.partner_type ?? "—";
        },
      },
      { key: "status", label: "Status" },
      {
        key: "actions",
        label: "Actions",
        render: (_, row) => (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                setSelectedRow(row);
                setForm({ ...row });
                setOverlayMode("edit");
                setErrorMessage(null);
              }}
              className="rounded-lg border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700"
            >
              Edit
            </button>
            <button
              onClick={() => {
                setSelectedRow(row);
                setSwitchRole(switchTargetOptions[role][0]);
                setOverlayMode("switch");
                setErrorMessage(null);
              }}
              className="rounded-lg border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700"
            >
              Switch Role
            </button>
            <button
              onClick={() => setConfirmState({ type: "delete", row })}
              className="rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-700"
            >
              Remove
            </button>
          </div>
        ),
      },
    ];

    return primaryColumns;
  }, [role]);

  async function runConfirmedAction() {
    if (!confirmState) return;

    setErrorMessage(null);

    try {
      if (confirmState.type === "create") {
        await createStakeholder(form);
        setForm(emptyForm(role));
        setShowCreateForm(false);
      }

      if (confirmState.type === "edit") {
        await updateStakeholder(confirmState.row.id, form);
        setSelectedRow(null);
        setOverlayMode(null);
      }

      if (confirmState.type === "delete") {
        await deleteStakeholder(confirmState.row.id);
        if (selectedRow?.id === confirmState.row.id) {
          setSelectedRow(null);
          setForm(emptyForm(role));
          setOverlayMode(null);
        }
      }

      if (confirmState.type === "switch") {
        await switchStakeholder({
          sourceRole: role,
          sourceId: confirmState.row.id,
          targetRole: confirmState.targetRole,
        });
        if (selectedRow?.id === confirmState.row.id) {
          setSelectedRow(null);
          setForm(emptyForm(role));
          setOverlayMode(null);
        }
      }

      setConfirmState(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Action failed.");
      setConfirmState(null);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!form.name?.trim()) {
      setErrorMessage("Name is required.");
      return;
    }

    setConfirmState(selectedRow ? { type: "edit", row: selectedRow } : { type: "create" });
  }

  const confirmation = (() => {
    if (!confirmState) return null;
    if (confirmState.type === "create") {
      return {
        title: `Confirm new ${titleCase(role.slice(0, -1))}`,
        description: `Create this ${role.slice(0, -1)} record now?`,
        confirmLabel: "Confirm create",
        loading: isCreating,
      };
    }
    if (confirmState.type === "edit") {
      return {
        title: `Confirm update for ${confirmState.row.name}`,
        description: `Save the changes to this ${role.slice(0, -1)} record?`,
        confirmLabel: "Confirm update",
        loading: isUpdating,
      };
    }
    if (confirmState.type === "delete") {
      return {
        title: `Confirm removal for ${confirmState.row.name}`,
        description: `This will mark the record inactive and remove its identity mapping if possible. Continue?`,
        confirmLabel: "Confirm remove",
        loading: isDeleting,
      };
    }
    return {
      title: `Confirm switch from ${titleCase(role.slice(0, -1))} to ${titleCase(confirmState.targetRole.slice(0, -1))}`,
      description: `This will create a new ${confirmState.targetRole.slice(0, -1)} record, update the identity mapping, and archive the current ${role.slice(0, -1)} record. Continue?`,
      confirmLabel: "Confirm switch",
      loading: isSwitching,
    };
  })();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">{title}</h1>
        <p className="mt-2 text-zinc-500">{description}</p>
      </div>

      {isError ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to load {role}.</p> : null}
      {errorMessage ? <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</p> : null}

      {!selectedRow && !showCreateForm && !overlayMode ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setShowCreateForm(true);
              setSelectedRow(null);
              setForm(emptyForm(role));
              setErrorMessage(null);
            }}
            className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white"
          >
            Add {titleCase(role.slice(0, -1))}
          </button>
        </div>
      ) : null}

      {showCreateForm ? (
        <SectionCard title={`Add ${titleCase(role.slice(0, -1))}`} description="Create a new record, then confirm it before saving.">
          <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
            <StakeholderFields fieldSet={fieldSet} form={form} setForm={setForm} />
            <div className="md:col-span-2 flex flex-wrap gap-3">
              <button type="submit" disabled={isCreating} className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">
                Review new record
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  setForm(emptyForm(role));
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

      <SectionCard title={`${title} records`} description="Manage records, statuses, and ownership roles.">
        {isLoading ? <p className="text-sm text-zinc-500">Loading {role}...</p> : <DataTable columns={columns} data={data} />}
      </SectionCard>

      <ActionOverlay
        open={overlayMode === "edit" && Boolean(selectedRow)}
        title={selectedRow ? `Edit ${selectedRow.name}` : "Edit record"}
        description="Adjust the current information, then review the changes before saving."
        onCloseAction={() => {
          setOverlayMode(null);
          setSelectedRow(null);
          setForm(emptyForm(role));
        }}
      >
        <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <StakeholderFields fieldSet={fieldSet} form={form} setForm={setForm} />
          <div className="md:col-span-2 flex flex-wrap gap-3">
            <button type="submit" disabled={isUpdating} className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">
              Review changes
            </button>
            <button
              type="button"
              onClick={() => {
                setOverlayMode(null);
                setSelectedRow(null);
                setForm(emptyForm(role));
              }}
              className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
            >
              Cancel
            </button>
          </div>
        </form>
      </ActionOverlay>

      <ActionOverlay
        open={overlayMode === "switch" && Boolean(selectedRow)}
        title={selectedRow ? `Switch ${selectedRow.name} to another role` : "Switch role"}
        description="Choose the target role, then confirm the switch." 
        onCloseAction={() => {
          setOverlayMode(null);
          setSelectedRow(null);
        }}
      >
        <div className="space-y-4">
          <label className="space-y-2 text-sm font-medium text-zinc-700">
            <span>Target role</span>
            <select
              value={switchRole}
              onChange={(event) => setSwitchRole(event.target.value as StakeholderRole)}
              className="block w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm font-normal"
            >
              {switchTargetOptions[role].map((option) => (
                <option key={option} value={option}>
                  {titleCase(option)}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => selectedRow && setConfirmState({ type: "switch", row: selectedRow, targetRole: switchRole })}
              disabled={isSwitching || !selectedRow}
              className="rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
            >
              Review switch
            </button>
            <button
              type="button"
              onClick={() => {
                setOverlayMode(null);
                setSelectedRow(null);
              }}
              className="rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700"
            >
              Cancel
            </button>
          </div>
        </div>
      </ActionOverlay>

      {confirmation ? (
        <ConfirmActionDialog
          open={Boolean(confirmState)}
          title={confirmation.title}
          description={confirmation.description}
          confirmLabel={confirmation.confirmLabel}
          loading={confirmation.loading}
          onCancelAction={() => setConfirmState(null)}
          onConfirmAction={runConfirmedAction}
        />
      ) : null}
    </div>
  );
}
