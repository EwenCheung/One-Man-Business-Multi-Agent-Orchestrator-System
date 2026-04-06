-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA public;

-- Enable RLS and create policies for all tables with owner_id
DO $$
DECLARE
  r RECORD;
  policy_exists boolean;
  tbl text;
  policy_name text;
BEGIN
  FOR r IN
    SELECT table_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = 'owner_id'
  LOOP
    tbl := r.table_name;
    policy_name := 'owner_policy_' || tbl;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);

    SELECT EXISTS(
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'public' AND tablename = tbl AND policyname = policy_name
    ) INTO policy_exists;

    IF NOT policy_exists THEN
      EXECUTE format($p$
        CREATE POLICY %I ON public.%I
          FOR ALL
          USING (owner_id = auth.uid())
          WITH CHECK (owner_id = auth.uid())
      $p$, policy_name, tbl);
    END IF;
  END LOOP;
END
$$ LANGUAGE plpgsql;

-- Special-case: profiles table uses id as owner
DO $$
DECLARE
  policy_exists boolean;
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='profiles') THEN
    EXECUTE 'ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY';

    SELECT EXISTS(
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'public' AND tablename = 'profiles' AND policyname = 'owner_policy_profiles'
    ) INTO policy_exists;

    IF NOT policy_exists THEN
      EXECUTE $p$
        CREATE POLICY owner_policy_profiles ON public.profiles
          FOR ALL
          USING (id = auth.uid())
          WITH CHECK (id = auth.uid())
      $p$;
    END IF;
  END IF;
END
$$ LANGUAGE plpgsql;
