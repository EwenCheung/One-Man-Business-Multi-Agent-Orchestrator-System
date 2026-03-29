export type CustomerRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  status: string | null;
};

export type SupplierRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  category: string | null;
  status: string | null;
};

export type InvestorRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  focus: string | null;
  status: string | null;
};

export type PartnerRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  partner_type: string | null;
  status: string | null;
};