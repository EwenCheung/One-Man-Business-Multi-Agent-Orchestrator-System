import type { CustomerRow, InvestorRow, PartnerRow, SupplierRow } from "@/lib/types";

export const stakeholderRoles = ["customers", "suppliers", "investors", "partners"] as const;

export type StakeholderRole = (typeof stakeholderRoles)[number];

export const roleTableMap: Record<StakeholderRole, StakeholderRole> = {
  customers: "customers",
  suppliers: "suppliers",
  investors: "investors",
  partners: "partners",
};

export const switchTargetOptions: Record<StakeholderRole, StakeholderRole[]> = {
  customers: ["suppliers", "investors", "partners"],
  suppliers: ["customers", "investors", "partners"],
  investors: ["customers", "suppliers", "partners"],
  partners: ["customers", "suppliers", "investors"],
};

export const stakeholderFieldLabels: Record<StakeholderRole, Array<{ key: string; label: string }>> = {
  customers: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "company", label: "Company" },
    { key: "status", label: "Status" },
    { key: "preference", label: "Preference" },
    { key: "notes", label: "Notes" },
  ],
  suppliers: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "category", label: "Category" },
    { key: "status", label: "Status" },
    { key: "contract_notes", label: "Contract notes" },
  ],
  investors: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "focus", label: "Focus" },
    { key: "status", label: "Status" },
    { key: "notes", label: "Notes" },
  ],
  partners: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "partner_type", label: "Partner type" },
    { key: "status", label: "Status" },
    { key: "notes", label: "Notes" },
  ],
};

export function appendSwitchNote(current: string | null | undefined, targetLabel: string) {
  const prefix = current?.trim() ? `${current.trim()}\n\n` : "";
  return `${prefix}Switched by owner to ${targetLabel} on ${new Date().toISOString()}.`;
}

export type StakeholderDataByRole = {
  customers: CustomerRow;
  suppliers: SupplierRow;
  investors: InvestorRow;
  partners: PartnerRow;
};
