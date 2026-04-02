import ProductsClient from "@/components/inventory/products-client";
import { getProducts } from "@/lib/api";

export default async function ProductsPage() {
  const products = await getProducts();

  return <ProductsClient initialData={products} />;
}
