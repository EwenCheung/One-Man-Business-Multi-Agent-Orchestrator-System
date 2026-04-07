import { getOwnerProfile } from "@/lib/api";
import ProfileClient from "@/components/profile/profile-client";

export default async function ProfilePage() {
  const profile = await getOwnerProfile();

  return <ProfileClient initialData={profile} />;
}
