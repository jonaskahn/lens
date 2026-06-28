export function usePaginatedQuery<T>(
  _key: string,
  fetcher: (params: { limit: number; cursor?: string }) => Promise<{
    items: T[];
    next_cursor: string | null;
  }>,
  limit = 50,
) {
  const cursor = ref<string | undefined>();
  const items: Ref<T[]> = ref([]) as Ref<T[]>;
  const nextCursor = ref<string | null>(null);
  const loading = ref(false);
  const error = ref<Error | null>(null);

  const fetchNext = async () => {
    loading.value = true;
    error.value = null;
    try {
      const result = await fetcher({ limit, cursor: cursor.value });
      items.value = [...items.value, ...result.items];
      nextCursor.value = result.next_cursor;
      cursor.value = result.next_cursor ?? undefined;
    } catch (e) {
      error.value = e as Error;
    } finally {
      loading.value = false;
    }
  };

  const fetchFirst = async () => {
    items.value = [];
    cursor.value = undefined;
    nextCursor.value = null;
    await fetchNext();
  };

  return {
    items,
    nextCursor,
    loading,
    error,
    fetchNext,
    fetchFirst,
  };
}
