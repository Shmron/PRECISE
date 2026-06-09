#!/bin/bash
# Fix /PALS permissions: owner-writes, group-reads
# Run with: sudo bash /home/rutendo/PRECISE/fix-pals-permissions.sh

echo "=== Fixing /PALS permissions ==="

# 1. Sticky bit on /PALS itself
chmod +t /PALS
echo "Sticky bit set on /PALS"

# 2. Set default ACL on /PALS AND every subdir inside it.
#    Access ACL stays rwx on shared dirs (users can still CREATE inside them).
#    Default ACL is rX only — so any new subfolder a user creates inherits
#    group read+execute, never group write.
setfacl -m d:g::rX,d:g:pals:rX /PALS
echo "Default ACL set on /PALS"

find /PALS -mindepth 1 -type d | while read dir; do
    setfacl -m d:g::rX,d:g:pals:rX "$dir"
done
echo "Default ACL propagated to all subdirectories"

# 3. Fix access ACL on existing user-owned dirs so right now
#    other group members lose write immediately (not just on new dirs).
find /PALS -mindepth 2 -type d | while read dir; do
    owner=$(stat -c '%U' "$dir")
    parent_owner=$(stat -c '%U' "$(dirname "$dir")")
    if [ "$owner" != "$parent_owner" ] || [ "$owner" != "rutendo" ]; then
        setfacl -m g::rX,g:pals:rX "$dir"
    fi
done

find /PALS -mindepth 2 -type f | while read f; do
    setfacl -m g::rX,g:pals:rX "$f"
done
echo "Existing user-created items restricted to group read-only"

echo ""
echo "=== Final state ==="
ls -la /PALS/
echo ""
getfacl /PALS
echo "Done."
