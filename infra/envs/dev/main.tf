# dev environment. Resources arrive from phase 3 (storage) onwards.
#
# Naming rule: every resource is named "${var.project}-dev-..." and every IAM role
# sets permissions_boundary to the "${var.project}-boundary-dev" policy from the
# bootstrap stack. The dev apply role cannot create anything outside that.
