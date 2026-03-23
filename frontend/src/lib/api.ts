import {
  customers,
  dailyDigest,
  dashboardStats,
  investors,
  partners,
  pendingApprovals,
  suppliers,
} from "./mock-data";

export async function getDashboardStats() {
  return dashboardStats;
}

export async function getPendingApprovals() {
  return pendingApprovals;
}

export async function getDailyDigest() {
  return dailyDigest;
}

export async function getCustomers() {
  return customers;
}

export async function getSuppliers() {
  return suppliers;
}

export async function getInvestors() {
  return investors;
}

export async function getPartners() {
  return partners;
}